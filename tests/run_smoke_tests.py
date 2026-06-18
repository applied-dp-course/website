#!/usr/bin/env python3
"""Serve the built ``_site`` and smoke-test every exported WASM interactive.

Discovers the same ``PrivacyPlot(...).embed()`` uses the build does, derives each
app's URL under ``_site``, and runs the headless-Chrome smoke test against it.
Exits non-zero if any interactive fails to render or respond to its sliders.
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
from smoke_wasm_browser import smoke_test  # noqa: E402


def main() -> None:
    output_root = SITE_ROOT / "_site"
    if not output_root.is_dir():
        raise SystemExit(f"built site not found: {output_root} (run `quarto render` first)")

    uses = build_interactives.discover_interactives(SITE_ROOT)
    if not uses:
        print("No libdpy interactive embeds discovered; nothing to smoke-test.")
        return

    relative_urls = []
    for use in uses:
        app_dir = use.output_directory.relative_to(SITE_ROOT)
        index = output_root / app_dir / "index.html"
        if not index.is_file():
            raise SystemExit(f"expected built app missing: {index}")
        relative_urls.append(app_dir.as_posix())

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(output_root)
    )
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()

        failures: list[str] = []
        for relative in relative_urls:
            url = f"http://127.0.0.1:{port}/{relative}/index.html"
            print(f"== smoke-testing {relative} ==", flush=True)
            try:
                smoke_test(url, timeout=300)
            except Exception as error:  # noqa: BLE001 - aggregate and report all
                print(f"FAIL {relative}: {error}", flush=True)
                failures.append(relative)
        httpd.shutdown()

    if failures:
        raise SystemExit(f"{len(failures)} interactive(s) failed: {failures}")
    print(f"All {len(relative_urls)} interactive(s) passed the WASM smoke test.")


if __name__ == "__main__":
    main()
