#!/usr/bin/env python3
"""Smoke-test that a rendered page actually loads deferred WASM iframes."""

from __future__ import annotations

import argparse
import posixpath
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from smoke_wasm_browser import (  # noqa: E402
    DevTools,
    _attach_devtools,
    _run_wasm_test,
    chrome_session,
    default_wasm_timeout,
)


def _deferred_wasm_urls(devtools: DevTools) -> list[str]:
    """Return WASM app URLs declared on the page before eager activation."""

    return (
        devtools.evaluate(
            """
            [...document.querySelectorAll('.libdpy-interactive iframe[data-libdpy-src]')]
              .map((frame) => frame.getAttribute('data-libdpy-src'))
              .filter((src) => src && (src.includes('apps/') || src.includes('_generated/apps/')))
            """
        )
        or []
    )


def _resolve_iframe_url(page_url: str, iframe_src: str) -> str:
    """Resolve a deferred iframe path relative to the rendered page URL."""

    if iframe_src.startswith("http"):
        return iframe_src
    parsed = urlparse(page_url)
    if iframe_src.startswith("/"):
        return f"{parsed.scheme}://{parsed.netloc}{iframe_src}"
    page_dir = PurePosixPath(parsed.path).parent.as_posix()
    normalized = posixpath.normpath(posixpath.join(page_dir, iframe_src))
    return f"{parsed.scheme}://{parsed.netloc}{normalized}"


def smoke_test_page(
    url: str,
    *,
    timeout: float | None = None,
    chrome_port: int | None = None,
) -> None:
    """Verify every deferred WASM embed on ``url`` by loading each app directly.

    Parent pages may host several marimo WASM iframes plus animation players.
    Loading every deferred iframe at once can surface benign COEP noise on the
    parent while the individual app bundles still work. We therefore discover
    ``data-libdpy-src`` targets from the rendered page and smoke-test each app
    URL in isolation (same check as the per-app WASM smoke tests).
    """

    timeout = default_wasm_timeout() if timeout is None else timeout

    def _run(chrome_port: int) -> None:
        devtools = _attach_devtools(chrome_port, url)
        try:
            deadline = __import__("time").time() + min(30.0, timeout * 0.1)
            discovered: list[str] = []
            while __import__("time").time() < deadline:
                discovered = _deferred_wasm_urls(devtools)
                if discovered:
                    break
                __import__("time").sleep(0.5)
        finally:
            devtools.close()

        if not discovered:
            raise RuntimeError(
                f"Full-page WASM smoke test failed: no deferred WASM iframe targets on {url}"
            )

        print(
            f"Full-page WASM smoke test found {len(discovered)} deferred interactive(s); "
            "running per-app checks..."
        )

        # Each deferred iframe is smoke-tested as a standalone WASM cold boot, so every
        # app needs the same budget as a single-app run — not a fraction of the total.
        per_app = timeout
        for iframe_src in discovered:
            resolved = _resolve_iframe_url(url, iframe_src)
            _run_wasm_test(chrome_port, resolved, per_app)

        print(
            f"Full-page WASM smoke test passed: {len(discovered)} iframe(s) loaded with "
            "Plotly trace data and responsive controls."
        )

    if chrome_port is not None:
        _run(chrome_port)
        return

    with chrome_session() as session_port:
        _run(session_port)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=None)
    args = parser.parse_args()
    smoke_test_page(args.url, timeout=args.timeout)


if __name__ == "__main__":
    main()
