#!/usr/bin/env python3
"""Headless-Chrome smoke test for an exported marimo WASM interactive."""

from __future__ import annotations

import argparse
import base64
import contextlib
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
        self.page_target_id: str | None = None

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


def _wait_for_debugger(port: int, timeout: float = 30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            return _json_request(f"http://127.0.0.1:{port}/json/version")
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Chrome remote debugger did not start")


def _attach_devtools(port: int, url: str, *, attempts: int = 4) -> DevTools:
    """Open a fresh tab for ``url`` and return a DevTools session with the core
    domains enabled.

    Retries the new-tab + websocket-connect handshake. On a loaded CI runner the
    connect to Chrome's debugger is flaky — a tight timeout surfaces as
    "Connection timed out" — and it gets worse for the 3rd/4th Chrome launched in
    a run, which is why the canvas tests (run after the WASM ones) failed while the
    WASM tests passed. Each retry opens a new tab on the *same* Chrome process.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        devtools = None
        try:
            target = _json_request(
                f"http://127.0.0.1:{port}/json/new?{url}",
                method="PUT",
            )
            devtools = DevTools(target["webSocketDebuggerUrl"])
            devtools.page_target_id = target.get("id")
            for domain in ("Page", "Runtime", "Log", "Network"):
                devtools.call(f"{domain}.enable")
            return devtools
        except Exception as error:  # noqa: BLE001 - retry transient connect failures
            last_error = error
            if devtools is not None:
                try:
                    devtools.close()
                except Exception:
                    pass
            if attempt < attempts:
                print(
                    f"  devtools attach attempt {attempt} failed ({error}); retrying...",
                    flush=True,
                )
                time.sleep(2.0)
    raise RuntimeError(f"could not attach DevTools to {url}: {last_error}")


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


@contextlib.contextmanager
def chrome_session(port: int | None = None):
    """Launch one Chrome with the debugger up and yield its port; terminate on exit.

    Reused across every app in a run. Relaunching Chrome per app is unstable on CI
    runners — it surfaces as "Chrome remote debugger did not start" or "Connection
    timed out", and gets worse for the 3rd/4th launch — so we pay the launch cost
    once and open a fresh tab per app instead (see _attach_devtools / _close_tab).
    The shared user-data-dir also lets the Pyodide/CDN cache warm across apps.
    """
    if not CHROME.exists():
        raise RuntimeError(f"Chrome not found at {CHROME}")
    port = _free_port() if port is None else port
    with tempfile.TemporaryDirectory(prefix="libdpy-chrome-") as profile, \
            tempfile.TemporaryFile(prefix="libdpy-chrome-stderr-") as chrome_err:
        # Capture Chrome's stderr to a file (not a PIPE, which could deadlock on a
        # long session) so a failed launch surfaces a real message.
        process = subprocess.Popen(
            _chrome_launch_command(profile, port),
            stdout=subprocess.DEVNULL,
            stderr=chrome_err,
        )
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
            yield port
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _close_tab(port: int, devtools: DevTools) -> None:
    """Close the app's tab so its kernel/memory is released between apps."""
    target_id = devtools.page_target_id
    if not target_id:
        return
    with contextlib.suppress(Exception):
        _json_request(f"http://127.0.0.1:{port}/json/close/{target_id}")


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
window.__buttons = () => window.__deepAll(document, []).filter(
  (e) => e.tagName && e.tagName.toLowerCase() === 'button' && e.textContent.trim());
window.__visible = (e) => e && e.getClientRects && e.getClientRects().length > 0;
window.__computeButtons = () => window.__buttons().filter((e) => {
  const label = e.textContent || e.innerText || e.getAttribute('aria-label') || '';
  return window.__visible(e) && /compute/i.test(label);
});
window.__roleCheckboxes = () => window.__deepAll(document, []).filter(
  (e) => e.getAttribute && e.getAttribute('role') === 'checkbox');
window.__plot = () => {
  const plots = window.__deepAll(document, []).filter(
    (e) => e.classList && e.classList.contains('js-plotly-plot'));
  return plots.find((p) => p.data && p.data.some(window.__traceHasData)) || plots[0] || null;
};
window.__dataLength = (value) => {
  if (value == null) return 0;
  if (typeof value.length === 'number') return value.length;
  if (Array.isArray(value.shape) && value.shape.length) {
    return value.shape.reduce((product, item) => product * item, 1);
  }
  if (typeof value.bdata === 'string') return value.bdata.length;
  return 0;
};
window.__traceHasData = (trace) => {
  return Boolean(
    trace && (
      window.__dataLength(trace.x) ||
      window.__dataLength(trace.y)
    )
  );
};
window.__valueSignature = (value) => {
  if (value == null) return null;
  if (Array.isArray(value)) return value;
  if (ArrayBuffer.isView(value)) return Array.from(value);
  if (typeof value !== 'object') return value;
  if (typeof value.length === 'number') {
    try {
      return Array.from(value);
    } catch (_error) {
      return String(value);
    }
  }
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, window.__valueSignature(value[key])])
  );
};
window.__plotSignature = (plot) => {
  if (!plot || !plot.data) return "";
  return JSON.stringify(plot.data.map((trace) => ({
    x: window.__valueSignature(trace.x),
    y: window.__valueSignature(trace.y),
    visible: trace.visible === undefined ? true : trace.visible,
  })));
};
window.__plotHasTraceData = () => {
  const plots = window.__deepAll(document, []).filter(
    (e) => e.classList && e.classList.contains('js-plotly-plot'));
  return plots.some((p) => p.data && p.data.some(window.__traceHasData));
};
window.__nudgeSlider = () => {
  const thumb = window.__thumbs()[0];
  if (!thumb) return false;
  thumb.focus();
  return true;
};
window.__deepText = () => {
  const parts = [document.body ? document.body.innerText : ''];
  window.__deepAll(document, []).forEach((e) => {
    if (e.shadowRoot) parts.push(e.shadowRoot.textContent || '');
  });
  return parts.join('\\n').replace(/\\n{3,}/g, '\\n\\n').slice(-4000);
};
true;
"""


def _plot_diagnostics(devtools: DevTools) -> str:
    return devtools.evaluate(
        """
        (function () {
          const sliders = (window.__sliders && window.__sliders().length) || 0;
          const thumbs = (window.__thumbs && window.__thumbs().length) || 0;
          const buttons = (window.__buttons && window.__buttons().length) || 0;
          const computeButtons = (window.__computeButtons && window.__computeButtons().length) || 0;
          const checkboxes = (window.__roleCheckboxes && window.__roleCheckboxes().length) || 0;
          const plots = window.__deepAll(document, []).filter(
            (e) => e.classList && e.classList.contains('js-plotly-plot'));
          const plot = window.__plot ? window.__plot() : null;
          const traceCount = plot && plot.data ? plot.data.length : 0;
          const traceLengths = plot && plot.data
            ? plot.data.map((trace) => Math.max(
                window.__dataLength(trace.x),
                window.__dataLength(trace.y)
              ))
            : [];
          return [
            `marimo sliders: ${sliders}`,
            `slider thumbs: ${thumbs}`,
            `buttons: ${buttons}`,
            `compute buttons: ${computeButtons}`,
            `checkboxes: ${checkboxes}`,
            `plotly divs: ${plots.length}`,
            `plot element: ${plot ? 'yes' : 'no'}`,
            `plot traces: ${traceCount}`,
            `max trace length: ${traceLengths.length ? Math.max(...traceLengths) : 0}`,
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
    reported_errors: set[str] = set()
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
            # The Pyodide kernel runs in a Web Worker; its exceptions (a failed
            # micropip install, a missing wheel dependency, an import error) never
            # reach the page. Surface kernel state + any *new* worker/page errors
            # each interval so a stalled boot is diagnosable from the CI log
            # instead of an opaque 8-minute "still waiting" silence.
            print("  still waiting for Plotly trace data...", flush=True)
            try:
                for line in _plot_diagnostics(devtools).splitlines():
                    print(f"    {line}", flush=True)
            except Exception:
                pass
            for error in _browser_errors(devtools):
                if error not in reported_errors:
                    reported_errors.add(error)
                    print(f"    browser error: {error}", flush=True)
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
    """Smoke-test a WASM app. With ``port`` set, reuse that running Chrome; otherwise
    launch a throwaway Chrome for this one app (standalone / CLI use)."""
    timeout = default_wasm_timeout() if timeout is None else timeout
    if port is None:
        with chrome_session() as session_port:
            _run_wasm_test(session_port, url, timeout)
    else:
        _run_wasm_test(port, url, timeout)


def _run_wasm_test(port: int, url: str, timeout: float) -> None:
    devtools = _attach_devtools(port, url)
    try:
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
            controls_ready_expr = (
                "(function () {"
                "  const sliders = window.__sliders().length;"
                "  const thumbs = window.__thumbs().length;"
                "  const computeButtons = window.__computeButtons().length;"
                "  const checkboxes = window.__roleCheckboxes().length;"
                "  if (sliders >= 2 && thumbs >= 2) return true;"
                "  return sliders >= 1 && thumbs >= 1 && (computeButtons >= 1 || checkboxes >= 1);"
                "})()"
            )
            sliders_ready = _wait_for(
                devtools,
                controls_ready_expr,
                timeout=slider_timeout,
                label="marimo sliders",
            )
            if not sliders_ready:
                errors = _browser_errors(devtools)
                visible_text = devtools.evaluate("window.__deepText()")
                raise RuntimeError(
                    "interactive did not finish loading marimo controls\n"
                    f"{_plot_diagnostics(devtools)}\n"
                    f"visible text:\n{visible_text}\n"
                    f"browser errors:\n{chr(10).join(errors) if errors else '(none captured)'}"
                )

            plot_timeout = max(60.0, timeout - slider_timeout)
            plot_ready = _wait_for_plot(devtools, plot_timeout)
            if not plot_ready:
                errors = _browser_errors(devtools)
                visible_text = devtools.evaluate("window.__deepText()")
                raise RuntimeError(
                    "interactive did not finish loading a Plotly figure with trace data\n"
                    f"{_plot_diagnostics(devtools)}\n"
                    f"visible text:\n{visible_text}\n"
                    f"browser errors:\n{chr(10).join(errors) if errors else '(none captured)'}"
                )

            changed_any = False
            slider_failures: list[str] = []
            thumb_count = int(devtools.evaluate("window.__thumbs().length") or 0)
            for index in range(min(2, thumb_count)):
                before = devtools.evaluate(
                    "(function () {"
                    "  const p = window.__plot();"
                    "  window.__before = window.__plotSignature(p);"
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
                    slider_failures.append(f"slider {index}: not found")
                    continue
                for _ in range(30):
                    _dispatch_arrow_right(devtools)
                changed = _wait_for(
                    devtools,
                    "(function () {"
                    "  const p = window.__plot();"
                    "  return p && window.__plotSignature(p) !== window.__before;"
                    "})()",
                    timeout=45,
                )
                if not changed:
                    slider_failures.append(f"slider {index}: no plot change")
                else:
                    changed_any = True

            if not changed_any:
                clicked = devtools.evaluate(
                    """
                    (function () {
                      const p = window.__plot();
                      window.__before = window.__plotSignature(p);
                      const buttons = window.__buttons();
                      const button = buttons.find((b) => /generate|resample/i.test(b.textContent))
                        || buttons[0];
                      if (!button) return false;
                      button.click();
                      return true;
                    })()
                    """
                )
                if clicked:
                    changed_any = bool(
                        _wait_for(
                            devtools,
                            "(function () {"
                            "  const p = window.__plot();"
                            "  return p && window.__plotSignature(p) !== window.__before;"
                            "})()",
                            timeout=45,
                        )
                    )
                    if not changed_any:
                        slider_failures.append("action button: no plot change")
                else:
                    slider_failures.append("action button: not found")

            if not changed_any:
                raise RuntimeError(
                    "tested sliders did not update the Plotly figure "
                    f"({'; '.join(slider_failures)})"
                )

            checkbox_count = int(devtools.evaluate("window.__roleCheckboxes().length") or 0)
            if checkbox_count:
                clicked = devtools.evaluate(
                    """
                    (function () {
                      const checkbox = window.__roleCheckboxes()[0];
                      const p = window.__plot();
                      window.__before = window.__plotSignature(p);
                      if (!checkbox) return false;
                      checkbox.click();
                      return true;
                    })()
                    """
                )
                if not clicked:
                    raise RuntimeError("failed to locate marimo checkbox")
                changed = _wait_for(
                    devtools,
                    "(function () {"
                    "  const p = window.__plot();"
                    "  return p && window.__plotSignature(p) !== window.__before;"
                    "})()",
                    timeout=45,
                )
                if not changed:
                    raise RuntimeError("marimo checkbox did not update the Plotly figure")

            compute_button_count = int(devtools.evaluate("window.__computeButtons().length") or 0)
            if compute_button_count:
                clicked = devtools.evaluate(
                    """
                    (function () {
                      const button = window.__computeButtons()[0];
                      const p = window.__plot();
                      window.__before = window.__plotSignature(p);
                      if (!button) return false;
                      button.click();
                      return true;
                    })()
                    """
                )
                if not clicked:
                    raise RuntimeError("failed to locate Compute ε marimo button")
                changed = _wait_for(
                    devtools,
                    "(function () {"
                    "  const p = window.__plot();"
                    "  return p && window.__plotSignature(p) !== window.__before;"
                    "})()",
                    timeout=45,
                )
                if not changed:
                    raise RuntimeError("Compute ε button did not update the Plotly figure")

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
                "WASM smoke test passed: sliders rendered and controls updated the Plotly figure."
            )
    finally:
        _close_tab(port, devtools)
        devtools.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=None)
    arguments = parser.parse_args()
    smoke_test(arguments.url, timeout=arguments.timeout)


if __name__ == "__main__":
    main()
