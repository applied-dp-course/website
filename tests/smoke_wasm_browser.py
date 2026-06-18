#!/usr/bin/env python3
"""Headless-Chrome smoke test for an exported marimo WASM interactive."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket


def _resolve_chrome() -> Path:
    """Locate Chrome/Chromium: $LIBDPY_CHROME, then PATH, then the macOS default."""
    override = os.environ.get("LIBDPY_CHROME")
    if override:
        return Path(override)
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chrome"):
        found = shutil.which(candidate)
        if found:
            return Path(found)
    return Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


CHROME = _resolve_chrome()


class DevTools:
    def __init__(self, websocket_url: str):
        self.socket = websocket.create_connection(
            websocket_url,
            timeout=5,
            origin="http://127.0.0.1",
            suppress_origin=True,
        )
        self.next_id = 1
        self.events: list[dict] = []
        self.enabled_sessions: set[str] = set()

    def call(
        self,
        method: str,
        params: dict | None = None,
        *,
        session_id: str | None = None,
    ) -> dict:
        request_id = self.next_id
        self.next_id += 1
        message = {"id": request_id, "method": method, "params": params or {}}
        if session_id is not None:
            message["sessionId"] = session_id
        self.socket.send(json.dumps(message))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                return message.get("result", {})
            self.events.append(message)

    def enable_attached_targets(self) -> None:
        sessions = [
            event.get("params", {}).get("sessionId")
            for event in self.events
            if event.get("method") == "Target.attachedToTarget"
        ]
        for session_id in sessions:
            if not session_id or session_id in self.enabled_sessions:
                continue
            self.enabled_sessions.add(session_id)
            self.call("Runtime.enable", session_id=session_id)
            self.call("Log.enable", session_id=session_id)

    def evaluate(self, expression: str):
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
        )
        remote_object = result["result"]
        if remote_object.get("subtype") == "error":
            raise RuntimeError(remote_object.get("description", expression))
        return remote_object.get("value")

    def drain(self) -> None:
        self.socket.settimeout(0.05)
        try:
            while True:
                self.events.append(json.loads(self.socket.recv()))
        except Exception:
            pass
        finally:
            self.socket.settimeout(5)

    def close(self) -> None:
        self.socket.close()


def _json_request(url: str, *, method: str = "GET"):
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def _wait_for_debugger(port: int, timeout: float = 10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return _json_request(f"http://127.0.0.1:{port}/json/version")
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Chrome remote debugger did not start")


def _wait_for(devtools: DevTools, expression: str, timeout: float = 90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = devtools.evaluate(expression)
            devtools.enable_attached_targets()
            if value:
                return value
        except Exception:
            pass
        time.sleep(0.5)
    return None


def _browser_errors(devtools: DevTools) -> list[str]:
    devtools.drain()
    errors = []
    for event in devtools.events:
        method = event.get("method")
        params = event.get("params", {})
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            errors.append(details.get("text", "Runtime exception"))
        elif method == "Log.entryAdded":
            entry = params.get("entry", {})
            if entry.get("level") == "error":
                errors.append(entry.get("text", "Console error"))
        elif method == "Network.loadingFailed":
            errors.append(
                f"Network failure: {params.get('errorText')} "
                f"({params.get('blockedReason', 'unblocked')})"
            )
    return errors


def smoke_test(url: str, *, port: int = 9224, timeout: float = 300) -> None:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found at {CHROME}")

    with tempfile.TemporaryDirectory(prefix="libdpy-wasm-chrome-") as profile, \
            tempfile.TemporaryFile(prefix="libdpy-wasm-chrome-stderr-") as chrome_err:
        # Capture Chrome's stderr to a file (not a PIPE, which could deadlock on a
        # long session) so a failed launch surfaces a real message instead of an
        # opaque "debugger did not start".
        process = subprocess.Popen(
            [
                str(CHROME),
                "--headless=new",
                "--disable-gpu",
                # Required on CI runners: the setup-chrome chromium has no SUID
                # sandbox helper, so Chrome silently fails to start without these.
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--remote-allow-origins=*",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile}",
                "about:blank",
            ],
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
            target = _json_request(
                f"http://127.0.0.1:{port}/json/new?{url}",
                method="PUT",
            )
            devtools = DevTools(target["webSocketDebuggerUrl"])
            for domain in ("Page", "Runtime", "Log", "Network"):
                devtools.call(f"{domain}.enable")
            devtools.call(
                "Target.setAutoAttach",
                {
                    "autoAttach": True,
                    "waitForDebuggerOnStart": False,
                    "flatten": True,
                },
            )

            # marimo renders mo.ui.slider as <marimo-slider> custom elements (Radix
            # UI, not native <input type=range>) and mounts the Plotly figure inside
            # a shadow root (<marimo-plotly>). Light-DOM selectors never match, so
            # every probe pierces shadow roots via these injected helpers.
            devtools.evaluate(
                """
                window.__deepAll = (root, acc) => {
                  const r = root || document;
                  if (r.shadowRoot) window.__deepAll(r.shadowRoot, acc);
                  r.querySelectorAll('*').forEach((el) => {
                    acc.push(el);
                    if (el.shadowRoot) window.__deepAll(el.shadowRoot, acc);
                  });
                  return acc;
                };
                window.__sliders = () => window.__deepAll(document, []).filter(
                  (e) => e.tagName && e.tagName.toLowerCase() === 'marimo-slider');
                window.__thumbs = () => window.__deepAll(document, []).filter(
                  (e) => e.getAttribute && e.getAttribute('role') === 'slider');
                window.__plot = () => window.__deepAll(document, []).find(
                  (e) => e.classList && e.classList.contains('js-plotly-plot'));
                true;
                """
            )

            ready = _wait_for(
                devtools,
                "window.__sliders().length >= 2 && window.__thumbs().length >= 2 "
                "&& (function () {"
                "  const p = window.__plot();"
                "  return !!(p && p.data && p.data[0] && p.data[0].y && p.data[0].y.length);"
                "})()",
                timeout=timeout,
            )
            if not ready:
                errors = _browser_errors(devtools)
                visible_text = devtools.evaluate("document.body.innerText.slice(-3000)")
                slider_count = devtools.evaluate(
                    "(window.__sliders && window.__sliders().length) || 0"
                )
                raise RuntimeError(
                    "interactive did not finish loading two sliders and a Plotly figure\n"
                    f"marimo sliders found: {slider_count}\n"
                    f"visible text:\n{visible_text}\n"
                    f"browser errors:\n{chr(10).join(errors) if errors else '(none captured)'}"
                )

            for index in (0, 1):
                before = devtools.evaluate(
                    "(function () {"
                    "  const p = window.__plot();"
                    "  window.__before = JSON.stringify(Array.from(p.data[0].y));"
                    "  return window.__before;"
                    "})()"
                )
                # Drive the Radix slider through its keyboard interface. The thumb is
                # a <span role="slider" tabindex="0"> in the marimo-slider shadow root;
                # focus it, then step right with *trusted* CDP key events (synthetic
                # JS KeyboardEvents are ignored by Radix). marimo re-runs make_figure.
                moved = devtools.evaluate(
                    f"""
                    (function () {{
                      const thumb = window.__thumbs()[{index}];
                      if (!thumb) return false;
                      thumb.focus();
                      return true;
                    }})()
                    """
                )
                if not moved:
                    raise RuntimeError(f"failed to locate marimo slider {index}")
                for _ in range(30):
                    for event_type in ("rawKeyDown", "keyUp"):
                        devtools.call(
                            "Input.dispatchKeyEvent",
                            {
                                "type": event_type,
                                "key": "ArrowRight",
                                "code": "ArrowRight",
                                "windowsVirtualKeyCode": 39,
                                "nativeVirtualKeyCode": 39,
                            },
                        )
                changed = _wait_for(
                    devtools,
                    "(function () {"
                    "  const p = window.__plot();"
                    "  return p && JSON.stringify(Array.from(p.data[0].y)) !== window.__before;"
                    "})()",
                    timeout=45,
                )
                if not changed:
                    raise RuntimeError(
                        f"slider {index} did not update the privacy bound"
                    )

            errors = _browser_errors(devtools)
            if errors:
                raise RuntimeError("browser errors:\n" + "\n".join(errors))

            screenshot = devtools.call(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": False},
            )
            Path("/tmp/libdpy-wasm-smoke.png").write_bytes(
                base64.b64decode(screenshot["data"])
            )
            print(
                "WASM smoke test passed: two sliders rendered and updated the Plotly figure."
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
    parser.add_argument("--timeout", type=float, default=300)
    arguments = parser.parse_args()
    smoke_test(arguments.url, timeout=arguments.timeout)


if __name__ == "__main__":
    main()
