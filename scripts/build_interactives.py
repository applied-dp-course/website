#!/usr/bin/env python3
"""Discover ``libdpy`` interactive specs and export their static WASM apps."""

from __future__ import annotations

import argparse
import ast
import base64
import csv
import hashlib
import importlib
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import libdpy
from libdpy.visualization.interactive import InteractiveSpec, marimo_app_source
from libdpy.visualization.privacy_plots import PrivacyPlot
from scipy import stats

SITE_ROOT = Path(__file__).resolve().parents[1]
GENERATED_ROOT = SITE_ROOT / "generated"
DISCOVERY_ROOTS = (
    "content/lectures",
    "blog",
    "tools",
)
# Root-level shell pages with embeds (not covered by DISCOVERY_ROOTS globs).
DISCOVERY_FILES = (
    "index.qmd",
)
MARIMO_VERSION = "0.23.9"
PYTHON_FENCE = re.compile(
    r"^```(?:\{python\}|python)\s*$\n(.*?)^```\s*$",
    re.MULTILINE | re.DOTALL,
)
SUPPORTED_DISTRIBUTIONS = {
    "norm": stats.norm,
    "laplace": stats.laplace,
    "uniform": stats.uniform,
}


@dataclass(frozen=True)
class InteractiveUse:
    source: Path
    spec: InteractiveSpec

    @property
    def output_directory(self) -> Path:
        return self.source.parent / "apps" / self.spec.artifact_name


def _python_blocks(path: Path) -> list[str]:
    if path.suffix == ".qmd":
        return PYTHON_FENCE.findall(path.read_text(encoding="utf-8"))
    if path.suffix == ".ipynb":
        notebook = json.loads(path.read_text(encoding="utf-8"))
        return [
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        ]
    return []


def _call_name(function: ast.expr) -> str | None:
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return None


def _literal(node: ast.expr):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError) as error:
        raise ValueError(
            f"interactive arguments must be literals: {ast.unparse(node)}"
        ) from error


def _distribution_types(node: ast.expr):
    if not isinstance(node, (ast.List, ast.Tuple)):
        raise ValueError("distribution_types must be a literal list or tuple")
    result = []
    for item in node.elts:
        name = _call_name(item)
        if name not in SUPPORTED_DISTRIBUTIONS:
            raise ValueError(
                f"unsupported distribution in PrivacyPlot: {ast.unparse(item)}"
            )
        result.append(SUPPORTED_DISTRIBUTIONS[name])
    return result


def _privacy_plot_spec(call: ast.Call) -> InteractiveSpec:
    if call.args:
        raise ValueError("PrivacyPlot discovery currently requires keyword arguments")
    arguments = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            raise ValueError("PrivacyPlot discovery does not support **kwargs")
        if keyword.arg == "distribution_types":
            arguments[keyword.arg] = _distribution_types(keyword.value)
        else:
            arguments[keyword.arg] = _literal(keyword.value)
    return PrivacyPlot(**arguments).spec()


def _privacy_plot_embed_warning(relative_path: str, node: ast.Call) -> str | None:
    if not _is_supported_privacy_plot_embed(node):
        return None
    constructor = node.func.value
    assert isinstance(constructor, ast.Call)
    try:
        _privacy_plot_spec(constructor)
    except ValueError:
        return (
            f"{relative_path}: PrivacyPlot(...).embed() uses non-literal arguments; "
            "register the app in a manifest instead "
            f"({ast.unparse(node)})"
        )
    return None


def _discovery_paths(site_root: Path) -> list[Path]:
    paths: list[Path] = []
    for relative in DISCOVERY_FILES:
        path = site_root / relative
        if path.is_file():
            paths.append(path)
    for root_name in DISCOVERY_ROOTS:
        root = site_root / root_name
        if not root.is_dir():
            continue
        paths.extend(sorted(path for path in root.glob("**/*.qmd") if path.is_file()))
        paths.extend(sorted(path for path in root.glob("**/*.ipynb") if path.is_file()))
    return paths


def _is_supported_privacy_plot_embed(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "embed":
        return False
    constructor = node.func.value
    if not isinstance(constructor, ast.Call):
        return False
    return _call_name(constructor.func) == "PrivacyPlot"


def discover_unsupported_embeds(site_root: Path = SITE_ROOT) -> list[str]:
    """Return warnings for ``.embed()`` calls that cannot be discovered statically."""

    warnings: list[str] = []
    for path in _discovery_paths(site_root):
        relative = path.relative_to(site_root).as_posix()
        for block in _python_blocks(path):
            try:
                tree = ast.parse(block)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute) or node.func.attr != "embed":
                    continue
                privacy_plot_warning = _privacy_plot_embed_warning(relative, node)
                if privacy_plot_warning is not None:
                    warnings.append(privacy_plot_warning)
                    continue
                if _is_supported_privacy_plot_embed(node):
                    continue
                warnings.append(
                    f"{relative}: unsupported .embed() call requires manifest registration "
                    f"({ast.unparse(node)})"
                )
    return warnings


def discover_interactives(site_root: Path = SITE_ROOT) -> list[InteractiveUse]:
    """Find literal ``PrivacyPlot(...).embed()`` calls under lecture, blog, and tool sources."""

    uses: dict[tuple[Path, str], InteractiveUse] = {}
    for path in _discovery_paths(site_root):
        for block in _python_blocks(path):
            try:
                tree = ast.parse(block)
            except SyntaxError:
                # IPython magics are valid lecture code but not Python AST input.
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not _is_supported_privacy_plot_embed(node):
                    continue
                constructor = node.func.value
                assert isinstance(constructor, ast.Call)
                try:
                    spec = _privacy_plot_spec(constructor)
                except ValueError:
                    continue
                use = InteractiveUse(source=path, spec=spec)
                uses[(path.parent, spec.artifact_name)] = use
    return list(uses.values())


def _wheel_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _package_files(package_root: Path, archive_root: Path):
    for path in sorted(package_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(package_root)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        yield path, archive_root / relative


def build_libdpy_wheel(output_directory: Path) -> Path:
    """Build a pure-Python wheel from the imported ``libdpy`` package."""

    bundled_packages = {
        "libdpy": Path(libdpy.__file__).resolve().parent,
        "plotly": Path(importlib.import_module("plotly").__file__).resolve().parent,
        "_plotly_utils": Path(importlib.import_module("_plotly_utils").__file__)
        .resolve()
        .parent,
        "narwhals": Path(importlib.import_module("narwhals").__file__).resolve().parent,
        "packaging": Path(importlib.import_module("packaging").__file__)
        .resolve()
        .parent,
    }
    version = libdpy.__version__
    distribution = f"libdpy-{version}"
    wheel_path = output_directory / f"{distribution}-py3-none-any.whl"
    output_directory.mkdir(parents=True, exist_ok=True)

    records: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for package_name, package_root in bundled_packages.items():
            for source, destination in _package_files(package_root, Path(package_name)):
                data = source.read_bytes()
                if destination == Path("plotly/__init__.py"):
                    data = data.replace(
                        b'importlib.metadata.version("plotly")',
                        b'"6.8.0"',
                    )
                archive.writestr(destination.as_posix(), data)
                records.append(
                    (destination.as_posix(), _wheel_hash(data), str(len(data)))
                )

        dist_info = f"{distribution}.dist-info"
        metadata = (
            "Metadata-Version: 2.1\n"
            "Name: libdpy\n"
            f"Version: {version}\n"
            "Summary: Applied Differential Privacy course library\n"
        ).encode()
        wheel = (
            "Wheel-Version: 1.0\n"
            "Generator: website/scripts/build_interactives.py\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n"
        ).encode()
        for filename, data in (
            (f"{dist_info}/METADATA", metadata),
            (f"{dist_info}/WHEEL", wheel),
        ):
            archive.writestr(filename, data)
            records.append((filename, _wheel_hash(data), str(len(data))))

        record_name = f"{dist_info}/RECORD"
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerows([*records, (record_name, "", "")])
        archive.writestr(record_name, buffer.getvalue().encode())
    return wheel_path


def _enable_tracebacks(index_html: Path) -> None:
    """Flip the exported marimo app's ``show_tracebacks`` config to ``true``.

    marimo defaults it to ``false``, so a kernel error in the install/import/figure
    chain is swallowed: the app hangs with no output and no console error (the Pyodide
    kernel runs in a Web Worker, so the exception never reaches the page). Enabling it
    makes a failed widget render its traceback instead of spinning forever — a visible
    error in production, and the signal the WASM smoke test needs to diagnose a stall.
    """
    text = index_html.read_text(encoding="utf-8")
    updated = text.replace('"show_tracebacks": false', '"show_tracebacks": true', 1)
    if updated != text:
        index_html.write_text(updated, encoding="utf-8")


def _export(use: InteractiveUse, wheel: Path, *, site_root: Path) -> None:
    source_directory = GENERATED_ROOT / "interactives_src" / use.spec.artifact_name
    public_directory = source_directory / "public"
    source_directory.mkdir(parents=True, exist_ok=True)
    public_directory.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wheel, public_directory / wheel.name)

    app_source = source_directory / "app.py"
    app_source.write_text(
        marimo_app_source(
            use.spec,
            wheel_filename=wheel.name,
            marimo_version=MARIMO_VERSION,
        ),
        encoding="utf-8",
    )

    output_directory = use.output_directory
    if output_directory.exists():
        shutil.rmtree(output_directory)
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "marimo",
            "export",
            "html-wasm",
            str(app_source),
            "--output",
            str(output_directory),
            "--mode",
            "run",
            "--no-show-code",
        ],
        cwd=site_root,
        check=True,
    )
    _enable_tracebacks(output_directory / "index.html")
    (output_directory / ".libdpy-interactive").write_text(
        f"{use.spec.name}\n{use.spec.artifact_name}\n",
        encoding="utf-8",
    )
    payload_mb = sum(
        path.stat().st_size for path in output_directory.rglob("*") if path.is_file()
    ) / (1024 * 1024)
    print(f"{use.spec.artifact_name} payload: {payload_mb:.1f} MB")
    if payload_mb > 20:
        print(
            f"WARNING: {use.spec.artifact_name} exceeds the 20 MB WASM payload warning budget.",
            file=sys.stderr,
        )


def _write_gallery(site_root: Path) -> Path:
    _SCRIPTS_DIR = Path(__file__).resolve().parent
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    import content_model
    import gallery

    catalog = content_model.load_catalog()
    entries = gallery.build_gallery_entries(catalog)
    destination = GENERATED_ROOT / "gallery.json"
    return gallery.write_gallery_json(entries, destination, site_root=site_root)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="print discovered artifacts without building them",
    )
    arguments = parser.parse_args()

    for warning in discover_unsupported_embeds():
        print(f"WARNING: {warning}", file=sys.stderr)

    uses = discover_interactives()
    if arguments.discover_only:
        if not uses:
            print("No libdpy interactive embeds discovered.")
        else:
            for use in uses:
                print(f"{use.source.relative_to(SITE_ROOT)} -> {use.spec.artifact_name}")
        return

    if uses:
        wheel = build_libdpy_wheel(GENERATED_ROOT / "wheels")
        for use in uses:
            _export(use, wheel, site_root=SITE_ROOT)
            print(
                f"Built {use.spec.artifact_name} for "
                f"{use.source.parent.relative_to(SITE_ROOT)}"
            )
    else:
        print("No libdpy interactive embeds discovered.")

    gallery_path = _write_gallery(SITE_ROOT)
    print(f"Wrote gallery catalog: {gallery_path.relative_to(SITE_ROOT)}")


if __name__ == "__main__":
    main()
