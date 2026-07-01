#!/usr/bin/env python3
"""Serve the built ``_site`` and smoke-test exported lecture interactives.

Discovers:
- marimo WASM apps from ``PrivacyPlot(...).embed()`` calls in lecture sources;
- external-app canvas apps declared in lecture manifests.

Exits non-zero if any interactive fails to render or respond to its controls.

For lecture-scoped validation, pass ``--slug <name>`` or ``--route <path>`` to run
only matching full-page WASM routes (skipping the site-wide per-app loop by default).
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import threading
import time
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_interactives  # noqa: E402
import content_model  # noqa: E402
import gallery  # noqa: E402
from smoke_canvas_browser import smoke_test as smoke_canvas  # noqa: E402
from smoke_wasm_browser import (  # noqa: E402
    chrome_session,
    default_wasm_timeout,
    smoke_test as smoke_wasm,
)

from libdpy.visualization.plot_inventory import FULL_PAGE_WASM_SMOKE_ROUTES  # noqa: E402
from smoke_full_page_wasm import smoke_test_page  # noqa: E402

# When the same marimo export is copied to home, site posts, tools, and lectures, smoke-test
# one canonical deployment per artifact id (prefer lecture paths).
_WASM_SMOKE_PATH_PRIORITY = (
    "_generated/apps/lecture-presentations/",
    "_generated/apps/blog-posts/",
    "content/tools/",
    "content/site-posts/",
    "_generated/apps/",
)


def _wasm_artifact_id(relative_path: str) -> str:
    return Path(relative_path).name


def dedupe_wasm_smoke_paths(wasm_paths: list[str]) -> list[str]:
    grouped: dict[str, list[str]] = {}
    for path in wasm_paths:
        grouped.setdefault(_wasm_artifact_id(path), []).append(path)

    canonical: list[str] = []
    for artifact_id in sorted(grouped):
        candidates = grouped[artifact_id]
        chosen = candidates[0]
        for prefix in _WASM_SMOKE_PATH_PRIORITY:
            for candidate in candidates:
                if candidate.startswith(prefix):
                    chosen = candidate
                    break
            else:
                continue
            break
        canonical.append(chosen)
    return canonical


def discover_smoke_targets(
    site_root: Path,
    output_root: Path,
) -> tuple[list[str], list[str]]:
    """Return ``(wasm_paths, canvas_paths)`` relative to ``output_root``.

    Browser-native apps come from ``_generated/gallery.json``. WASM apps are the union of
    gallery-declared lecture apps and every ``PrivacyPlot(...).embed()`` export discovered
    in site sources (home page, blog posts, standalone tools, etc.).
    """

    wasm_paths: set[str] = set()
    canvas_paths: set[str] = set()

    gallery_path = site_root / "_generated" / "gallery.json"
    if gallery_path.is_file():
        for entry in gallery.load_gallery_json(gallery_path):
            relative = entry.href.strip("/")
            index = output_root / relative / "index.html"
            if entry.runtime in {"external-app", "browser-native"}:
                if not index.is_file():
                    raise SystemExit(f"expected built canvas app missing: {index}")
                canvas_paths.add(relative)
            elif entry.runtime == "wasm-marimo" and entry.source_kind == "lecture":
                if not index.is_file():
                    raise SystemExit(f"expected built WASM app missing: {index}")
                wasm_paths.add(relative)

    for use in build_interactives.discover_interactives(site_root):
        relative = build_interactives.output_directory_for(use, site_root).relative_to(
            site_root
        ).as_posix()
        index = output_root / relative / "index.html"
        if not index.is_file():
            raise SystemExit(f"expected built WASM app missing: {index}")
        wasm_paths.add(relative)

    return dedupe_wasm_smoke_paths(sorted(wasm_paths)), sorted(canvas_paths)


def discover_wasm_app_paths(site_root: Path, output_root: Path) -> list[str]:
    wasm_paths, _canvas_paths = discover_smoke_targets(site_root, output_root)
    return wasm_paths


def discover_canvas_app_paths(output_root: Path) -> list[str]:
    _wasm_paths, canvas_paths = discover_smoke_targets(SITE_ROOT, output_root)
    return canvas_paths


class _SiteHandler(http.server.SimpleHTTPRequestHandler):
    """Serve ``_site`` and swallow root ``/favicon.ico`` requests from headless Chrome."""

    def end_headers(self) -> None:
        # marimo/Pyodide WASM expects cross-origin isolation when loading the worker.
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        super().end_headers()

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def log_message(self, format: str, *args) -> None:
        return


def discover_full_page_wasm_routes() -> list[str]:
    """Return rendered routes that should pass ``smoke_full_page_wasm``."""

    return list(FULL_PAGE_WASM_SMOKE_ROUTES)


def filter_full_page_wasm_routes(
    routes: list[str],
    *,
    slug: str | None = None,
    selected: tuple[str, ...] = (),
) -> list[str]:
    """Return the subset of ``routes`` selected by explicit paths or a slug filter."""

    if selected:
        known = set(routes)
        unknown = [route for route in selected if route not in known]
        if unknown:
            raise SystemExit(
                "unknown full-page WASM route(s): "
                + ", ".join(unknown)
                + ". Known routes: "
                + ", ".join(routes)
            )
        return list(selected)
    if slug:
        matched = [route for route in routes if slug in route]
        if not matched:
            raise SystemExit(
                f"no full-page WASM routes match slug {slug!r}. "
                f"Known routes: {', '.join(routes)}"
            )
        return matched
    return routes


def shard_items(items: list[str], index: int, count: int) -> list[str]:
    """Return the ``index`` shard of ``items`` split across ``count`` workers."""

    if count <= 1:
        return items
    if index < 0 or index >= count:
        raise SystemExit(f"shard index must be in [0, {count}), got {index}")
    return [item for offset, item in enumerate(items) if offset % count == index]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--route",
        action="append",
        default=[],
        metavar="ROUTE",
        help=(
            "Smoke only this rendered full-page route (repeatable). "
            "Example: content/blog-posts/private-estimation/post.html"
        ),
    )
    parser.add_argument(
        "--slug",
        metavar="SLUG",
        help="Smoke full-page routes whose path contains this slug (e.g. private-estimation).",
    )
    parser.add_argument(
        "--skip-per-app",
        action="store_true",
        help="Skip standalone per-app WASM/canvas smoke tests.",
    )
    parser.add_argument(
        "--include-per-app",
        action="store_true",
        help="Also run standalone per-app smoke when --route or --slug is set.",
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        default=0,
        help="Zero-based shard index for parallel nightly smoke (default: 0).",
    )
    parser.add_argument(
        "--shard-count",
        type=int,
        default=1,
        help="Number of smoke shards (default: 1, no sharding).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    output_root = SITE_ROOT / "_site"
    if not output_root.is_dir():
        raise SystemExit(f"built site not found: {output_root} (run `quarto render` first)")

    scoped = bool(args.route or args.slug)
    skip_per_app = args.skip_per_app or (scoped and not args.include_per_app)

    wasm_urls: list[str] = []
    canvas_urls: list[str] = []
    if not skip_per_app:
        wasm_urls, canvas_urls = discover_smoke_targets(SITE_ROOT, output_root)

    page_routes = filter_full_page_wasm_routes(
        discover_full_page_wasm_routes(),
        slug=args.slug,
        selected=tuple(args.route),
    )
    relative_urls = wasm_urls + canvas_urls
    if args.shard_count > 1:
        relative_urls = shard_items(relative_urls, args.shard_index, args.shard_count)
        if args.shard_index != 0:
            page_routes = []
        print(
            f"Smoke shard {args.shard_index + 1}/{args.shard_count}: "
            f"{len(relative_urls)} per-app target(s)"
            + (f", {len(page_routes)} full-page route(s)" if page_routes else ""),
            flush=True,
        )
    if not relative_urls and not page_routes:
        print("No lecture interactives or full-page WASM routes discovered; nothing to smoke-test.")
        return

    if scoped:
        print(
            "Scoped smoke run: "
            f"{len(page_routes)} full-page route(s)"
            + ("" if skip_per_app else f", plus {len(relative_urls)} per-app target(s)"),
            flush=True,
        )

    handler = functools.partial(_SiteHandler, directory=str(output_root))
    failures: list[str] = []
    page_failures: list[str] = []

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as httpd:
        httpd.daemon_threads = True
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        with chrome_session() as chrome_port:
            if relative_urls:
                for relative in relative_urls:
                    url = f"http://127.0.0.1:{port}/{relative}/index.html"
                    smoke = smoke_canvas if relative in canvas_urls else smoke_wasm
                    label = "canvas" if relative in canvas_urls else "wasm"
                    print(f"== smoke-testing {label} {relative} ==", flush=True)
                    timeout = default_wasm_timeout() if label == "wasm" else 60
                    attempts = 2 if label == "wasm" else 1
                    for attempt in range(1, attempts + 1):
                        try:
                            smoke(url, port=chrome_port, timeout=timeout)
                            break
                        except Exception as error:  # noqa: BLE001 - aggregate and report all
                            if attempt < attempts:
                                print(
                                    f"  attempt {attempt} failed ({error}); retrying...",
                                    flush=True,
                                )
                                time.sleep(2.0)
                                continue
                            print(f"FAIL {relative}: {error}", flush=True)
                            failures.append(relative)

            for route in page_routes:
                page_path = output_root / route
                if not page_path.is_file():
                    page_failures.append(f"{route} (missing rendered page)")
                    continue
                url = f"http://127.0.0.1:{port}/{route}"
                print(f"== smoke-testing full-page wasm {route} ==", flush=True)
                try:
                    smoke_test_page(url, timeout=default_wasm_timeout(), chrome_port=chrome_port)
                except Exception as error:  # noqa: BLE001 - aggregate and report all
                    print(f"FAIL full-page {route}: {error}", flush=True)
                    page_failures.append(route)

        httpd.shutdown()

    failures.extend(page_failures)

    if failures:
        raise SystemExit(f"{len(failures)} interactive(s) failed: {failures}")
    page_count = len(page_routes)
    print(
        f"All smoke tests passed: {len(relative_urls)} interactive(s) "
        f"({len(wasm_urls)} WASM, {len(canvas_urls)} canvas)"
        f"{f', {page_count} full-page WASM route(s)' if page_count else ''}."
    )


if __name__ == "__main__":
    main()
