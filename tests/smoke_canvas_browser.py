#!/usr/bin/env python3
"""Headless-Chrome smoke test for browser-native canvas lecture apps."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import tempfile
import time
from pathlib import Path

from smoke_wasm_browser import (
    CHROME,
    DevTools,
    _attach_devtools,
    _browser_errors,
    _chrome_launch_command,
    _free_port,
    _wait_for,
    _wait_for_debugger,
)


def _canvas_signature(devtools: DevTools) -> str:
    return devtools.evaluate(
        """
        (function () {
          const canvas = document.querySelector("canvas");
          if (!canvas) return "";
          const ctx = canvas.getContext("2d");
          const { width, height } = canvas;
          const data = ctx.getImageData(0, 0, width, height).data;
          let hash = 0;
          for (let i = 0; i < data.length; i += 97) {
            hash = ((hash << 5) - hash + data[i]) | 0;
          }
          return `${width}x${height}:${hash}`;
        })()
        """
    )


def smoke_test(url: str, *, port: int | None = None, timeout: float = 60) -> None:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found at {CHROME}")

    port = _free_port() if port is None else port

    with tempfile.TemporaryDirectory(prefix="libdpy-canvas-chrome-") as profile, \
            tempfile.TemporaryFile(prefix="libdpy-canvas-chrome-stderr-") as chrome_err:
        process = subprocess.Popen(
            _chrome_launch_command(profile, port),
            stdout=subprocess.DEVNULL,
            stderr=chrome_err,
        )
        devtools = None
        try:
            try:
                _wait_for_debugger(port)
            except RuntimeError as exc:
                if process.poll() is not None:
                    chrome_err.seek(0)
                    err = chrome_err.read().decode("utf-8", "replace")
                    tail = "\n".join(err.strip().splitlines()[-8:])
                    raise RuntimeError(
                        f"{exc} (Chrome exited {process.returncode}): {tail}"
                    ) from exc
                raise
            devtools = _attach_devtools(port, url)

            ready = _wait_for(
                devtools,
                "(function () {"
                "  const canvas = document.querySelector('canvas');"
                "  const alpha = document.getElementById('alpha');"
                "  const alphaValue = document.getElementById('alpha-value');"
                "  if (!canvas || !alpha || !alphaValue || !alphaValue.textContent) return false;"
                "  const ctx = canvas.getContext('2d');"
                "  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;"
                "  for (let i = 0; i < data.length; i += 4) {"
                "    if (data[i] < 250 || data[i + 1] < 250 || data[i + 2] < 250) return true;"
                "  }"
                "  return false;"
                "})()",
                timeout=timeout,
            )
            if not ready:
                errors = _browser_errors(devtools)
                visible_text = devtools.evaluate("document.body.innerText.slice(-3000)")
                raise RuntimeError(
                    "canvas app did not finish loading a canvas and alpha controls\n"
                    f"visible text:\n{visible_text}\n"
                    f"browser errors:\n{chr(10).join(errors) if errors else '(none captured)'}"
                )

            before_readout = devtools.evaluate(
                "document.getElementById('alpha-value').textContent"
            )
            before_signature = _canvas_signature(devtools)
            changed = devtools.evaluate(
                """
                (function () {
                  const alpha = document.getElementById('alpha');
                  const next = Math.min(Number(alpha.max), Number(alpha.value) + 0.25);
                  alpha.value = String(next);
                  alpha.dispatchEvent(new Event('input', { bubbles: true }));
                  return true;
                })()
                """
            )
            if not changed:
                raise RuntimeError("failed to move the alpha slider")

            updated = _wait_for(
                devtools,
                "(function () {"
                "  const readout = document.getElementById('alpha-value').textContent;"
                f"  return readout && readout !== {json.dumps(before_readout)};"
                "})()",
                timeout=15,
            )
            after_signature = _canvas_signature(devtools)
            if not updated and before_signature == after_signature:
                raise RuntimeError("alpha slider did not update the canvas readout or drawing")

            errors = _browser_errors(devtools)
            if errors:
                raise RuntimeError("browser errors:\n" + "\n".join(errors))

            screenshot = devtools.call(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": False},
            )
            Path("/tmp/libdpy-canvas-smoke.png").write_bytes(
                base64.b64decode(screenshot["data"])
            )
            print(
                "Canvas smoke test passed: canvas rendered and responded to the alpha slider."
            )
        finally:
            if devtools is not None:
                devtools.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=60)
    arguments = parser.parse_args()
    smoke_test(arguments.url, timeout=arguments.timeout)


if __name__ == "__main__":
    main()
