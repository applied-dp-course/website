#!/usr/bin/env python3
"""Headless-Chrome smoke test for an exported marimo WASM interactive."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket


def default_wasm_timeout() -> float:
    """Pyodide cold boot + scipy/plotly import is much slower on CI runners."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return 600.0
    return 300.0


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


def _wait_for(
    devtools: DevTools,
    expression: str,
    timeout: float = 90,
    *,
    label: str = "",
) -> bool | None:
    deadline = time.monotonic() + timeout
    next_log = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        try:
            value = devtools.evaluate(expression)
            devtools.enable_attached_targets()
            if value:
                return value
        except Exception:
            pass
        now = time.monotonic()
        if label and now >= next_log:
            print(f"  still waiting for {label}...", flush=True)
            next_log = now + 15.0
        time.sleep(0.5)
    return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _use_headless() -> bool:
    """Headless Linux Chrome often never finishes Plotly/Pyodide; xvfb uses headed mode."""
    if os.environ.get("LIBDPY_HEADLESS", "1").strip().lower() in {"0", "false", "no"}:
        return False
    return True


def _chrome_launch_command(profile: str, port: int) -> list[str]:
    command = [str(CHROME)]
    if _use_headless():
        command.append("--headless=new")
        command.append("--disable-gpu")
    command.extend(
        [
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
        ]
    )
    return command


_PLOT_HELPERS_JS = """
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
window.__plot = () => {
  const plots = window.__deepAll(document, []).filter(
    (e) => e.classList && e.classList.contains('js-plotly-plot'));
  return plots.find(
    (p) => p.data && p.data[0] && p.data[0].y && p.data[0].y.length
  ) || plots[0] || null;
};
window.__plotHasTraceData = () => {
  const plots = window.__deepAll(document, []).filter(
    (e) => e.classList && e.classList.contains('js-plotly-plot'));
  return plots.some(
    (p) => p.data && p.data[0] && p.data[0].y && p.data[0].y.length
  );
};
window.__nudgeSlider = () => {
  const thumb = window.__thumbs()[0];
  if (!thumb) return false;
  thumb.focus();
  return true;
};
true;
"""


def _plot_diagnostics(devtools: DevTools) -> str:
    return devtools.evaluate(
        """
        (function () {
          const sliders = (window.__sliders && window.__sliders().length) || 0;
          const thumbs = (window.__thumbs && window.__thumbs().length) || 0;
          const plots = window.__deepAll(document, []).filter(
            (e) => e.classList && e.classList.contains('js-plotly-plot'));
          const plot = window.__plot ? window.__plot() : null;
          const traceCount = plot && plot.data ? plot.data.length : 0;
          const yLength = plot && plot.data && plot.data[0] && plot.data[0].y
            ? plot.data[0].y.length
            : 0;
          return [
            `marimo sliders: ${sliders}`,
            `slider thumbs: ${thumbs}`,
            `plotly divs: ${plots.length}`,
            `plot element: ${plot ? 'yes' : 'no'}`,
            `plot traces: ${traceCount}`,
            `first trace y length: ${yLength}`,
            `crossOriginIsolated: ${window.crossOriginIsolated}`,
          ].join('\\n');
        })()
        """
    )


def _dispatch_arrow_right(devtools: DevTools) -> None:
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


def _wait_for_plot(devtools: DevTools, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    next_log = time.monotonic() + 15.0
    next_nudge = time.monotonic() + 8.0
    while time.monotonic() < deadline:
        try:
            if devtools.evaluate("window.__plotHasTraceData()"):
                return True
            devtools.enable_attached_targets()
        except Exception:
            pass
        now = time.monotonic()
        if now >= next_nudge:
            try:
                if devtools.evaluate("window.__nudgeSlider()"):
                    _dispatch_arrow_right(devtools)
            except Exception:
                pass
            next_nudge = now + 8.0
        if now >= next_log:
            print("  still waiting for Plotly trace data...", flush=True)
            next_log = now + 15.0
        time.sleep(0.5)
    return False


def _browser_errors(devtools: DevTools) -> list[str]:
    devtools.drain()
    errors = []
    for event in devtools.events:
        method = event.get("method")
        params = event.get("params", {})
        if method == "Runtime.exceptionThrown":
            details = params.get("exceptionDetails", {})
            errors.append(details.get("text", "Runtime exception"))
        elif method == "Runtime.consoleAPICalled":
            if params.get("type") == "error":
                args = params.get("args", [])
                rendered = " ".join(
                    str(arg.get("value", arg.get("description", arg))) for arg in args
                )
                errors.append(f"console.error: {rendered}")
        elif method == "Log.entryAdded":
            entry = params.get("entry", {})
            if entry.get("level") == "error":
                errors.append(entry.get("text", "Console error"))
        elif method == "Network.loadingFailed":
            url = params.get("request", {}).get("url") or params.get("documentURL", "")
            errors.append(
                f"Network failure: {params.get('errorText')} "
                f"({params.get('blockedReason', 'unblocked')}) {url}".strip()
            )
        elif method == "Network.responseReceived":
            response = params.get("response", {})
            url = response.get("url", "")
            status = response.get("status")
            if "libdpy-" in url and url.endswith(".whl") and status != 200:
                errors.append(f"libdpy wheel HTTP {status}: {url}")
    return errors


def smoke_test(url: str, *, port: int | None = None, timeout: float | None = None) -> None:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found at {CHROME}")

    timeout = default_wasm_timeout() if timeout is None else timeout
    port = _free_port() if port is None else port

    with tempfile.TemporaryDirectory(prefix="libdpy-wasm-chrome-") as profile, \
            tempfile.TemporaryFile(prefix="libdpy-wasm-chrome-stderr-") as chrome_err:
        # Capture Chrome's stderr to a file (not a PIPE, which could deadlock on a
        # long session) so a failed launch surfaces a real message instead of an
        # opaque "debugger did not start".
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
            devtools.evaluate(_PLOT_HELPERS_JS)

            slider_timeout = min(120.0, timeout * 0.35)
            sliders_ready = _wait_for(
                devtools,
                "window.__sliders().length >= 2 && window.__thumbs().length >= 2",
                timeout=slider_timeout,
                label="marimo sliders",
            )
            if not sliders_ready:
                errors = _browser_errors(devtools)
                visible_text = devtools.evaluate("document.body.innerText.slice(-3000)")
                raise RuntimeError(
                    "interactive did not finish loading two marimo sliders\n"
                    f"{_plot_diagnostics(devtools)}\n"
                    f"visible text:\n{visible_text}\n"
                    f"browser errors:\n{chr(10).join(errors) if errors else '(none captured)'}"
                )

            plot_timeout = max(60.0, timeout - slider_timeout)
            plot_ready = _wait_for_plot(devtools, plot_timeout)
            if not plot_ready:
                errors = _browser_errors(devtools)
                visible_text = devtools.evaluate("document.body.innerText.slice(-3000)")
                raise RuntimeError(
                    "interactive did not finish loading a Plotly figure with trace data\n"
                    f"{_plot_diagnostics(devtools)}\n"
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
                    _dispatch_arrow_right(devtools)
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
    parser.add_argument("--timeout", type=float, default=None)
    arguments = parser.parse_args()
    smoke_test(arguments.url, timeout=arguments.timeout)


if __name__ == "__main__":
    main()
