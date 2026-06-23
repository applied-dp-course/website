#!/usr/bin/env python3
"""Serve the built ``_site`` and smoke-test exported lecture interactives.

Discovers:
- marimo WASM apps from ``PrivacyPlot(...).embed()`` calls in lecture sources;
- browser-native canvas apps declared in lecture manifests.

Exits non-zero if any interactive fails to render or respond to its controls.
"""

from __future__ import annotations

import functools
import http.server
import socketserver
import sys
import threading
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
            if entry.runtime == "browser-native":
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


def main() -> None:
    output_root = SITE_ROOT / "_site"
    if not output_root.is_dir():
        raise SystemExit(f"built site not found: {output_root} (run `quarto render` first)")

    wasm_urls, canvas_urls = discover_smoke_targets(SITE_ROOT, output_root)
    relative_urls = wasm_urls + canvas_urls
    if not relative_urls:
        print("No lecture interactives discovered; nothing to smoke-test.")
        return

    handler = functools.partial(_SiteHandler, directory=str(output_root))
    # Threaded: a headed CI browser opens many parallel connections (marimo assets
    # plus the multi-MB libdpy wheel the figure cell's micropip.install blocks on).
    # A single-threaded server serializes those, which can stall the WASM boot on a
    # slow runner even though it keeps up locally.
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler) as httpd:
        httpd.daemon_threads = True
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        failures: list[str] = []
        # Launch Chrome once and open a tab per app. Relaunching Chrome per app is
        # unstable on CI ("debugger did not start" / "Connection timed out", worsening
        # for later launches); one long-lived browser is reliable and faster.
        with chrome_session() as chrome_port:
            for relative in relative_urls:
                url = f"http://127.0.0.1:{port}/{relative}/index.html"
                smoke = smoke_canvas if relative in canvas_urls else smoke_wasm
                label = "canvas" if relative in canvas_urls else "wasm"
                print(f"== smoke-testing {label} {relative} ==", flush=True)
                try:
                    timeout = default_wasm_timeout() if label == "wasm" else 60
                    smoke(url, port=chrome_port, timeout=timeout)
                except Exception as error:  # noqa: BLE001 - aggregate and report all
                    print(f"FAIL {relative}: {error}", flush=True)
                    failures.append(relative)
        httpd.shutdown()

    if failures:
        raise SystemExit(f"{len(failures)} interactive(s) failed: {failures}")
    print(
        f"All {len(relative_urls)} interactive(s) passed smoke tests "
        f"({len(wasm_urls)} WASM, {len(canvas_urls)} canvas)."
    )


if __name__ == "__main__":
    main()
