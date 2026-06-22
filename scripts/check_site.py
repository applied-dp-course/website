#!/usr/bin/env python3
"""Post-render and post-deploy verification for the course site."""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import assert_private_content
import colab
import content_model
import gallery
import write_redirects


TOP_LEVEL_ROUTES = (
    "index.html",
    "schedule.html",
    "lectures.html",
    "assignments.html",
    "tools.html",
    "blog/index.html",
    "syllabus.html",
    "archive.html",
    "about.html",
)

# Maintainer-facing root docs that must never render into the published site.
FORBIDDEN_PUBLISHED_NAMES = (
    "README.md",
    "TODO.md",
    "STATUS.md",
)

COLAB_URL_PATTERN = re.compile(
    r"https://colab\.research\.google\.com/github/[^\"'\s<>]+",
    re.IGNORECASE,
)


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value for name, value in attrs if value is not None}
        if tag == "a" and "href" in attr_map:
            self.links.append(("href", attr_map["href"]))
        elif tag in {"img", "script", "iframe"} and "src" in attr_map:
            self.links.append(("src", attr_map["src"]))


def required_routes(catalog: content_model.ContentCatalog) -> tuple[str, ...]:
    routes = list(TOP_LEVEL_ROUTES)
    for legacy_path, _target in write_redirects.collect_legacy_redirects(
        catalog,
        output_root=content_model.SITE_ROOT / "_site",
    ):
        routes.append(legacy_path.relative_to(content_model.SITE_ROOT / "_site").as_posix())
    for lecture in catalog.lectures:
        base = f"{content_model.LECTURES_URL_PREFIX}/{lecture.slug}"
        for surface in (lecture.surfaces.learn, lecture.surfaces.presentation):
            stem = Path(surface).stem
            routes.append(f"{base}/{stem}.html")
    deduped = sorted(set(routes))
    return tuple(deduped)


def _is_external_href(href: str) -> bool:
    if not href or href.startswith("#"):
        return True
    lowered = href.lower()
    return lowered.startswith(
        ("http://", "https://", "mailto:", "javascript:", "data:", "//")
    )


def resolve_internal_target(site_root: Path, page_path: Path, href: str) -> Path | None:
    if _is_external_href(href):
        return None

    target = href.split("#", 1)[0].split("?", 1)[0]
    if not target:
        return page_path.resolve()

    site_root = site_root.resolve()
    page_path = page_path.resolve()

    if target.startswith("/"):
        candidate = site_root / target.lstrip("/")
    else:
        candidate = (page_path.parent / target).resolve()

    try:
        candidate.relative_to(site_root)
    except ValueError:
        return None
    return candidate


def target_exists(site_root: Path, target: Path) -> bool:
    if target.is_file():
        return True
    if target.is_dir() and (target / "index.html").is_file():
        return True
    if not target.suffix and target.with_suffix(".html").is_file():
        return True
    return False


def check_internal_links(site_root: Path) -> list[str]:
    errors: list[str] = []
    site_root = site_root.resolve()
    for html_path in sorted(site_root.rglob("*.html")):
        if write_redirects.REDIRECT_MARKER in html_path.read_text(encoding="utf-8"):
            continue

        parser = _LinkExtractor()
        parser.feed(html_path.read_text(encoding="utf-8"))
        for _kind, href in parser.links:
            target = resolve_internal_target(site_root, html_path, href)
            if target is None:
                continue
            if not target_exists(site_root, target):
                rel_page = html_path.relative_to(site_root).as_posix()
                rel_target = target.relative_to(site_root).as_posix()
                errors.append(
                    f"{rel_page}: broken internal {href!r} "
                    f"(resolved to {rel_target})"
                )
    return errors


def check_required_routes_local(site_root: Path, routes: Iterable[str]) -> list[str]:
    errors: list[str] = []
    for route in routes:
        target = site_root / route
        if not target.is_file():
            errors.append(f"missing required route: {route}")
    return errors


def check_legacy_redirects_local(
    catalog: content_model.ContentCatalog,
    site_root: Path,
) -> list[str]:
    errors: list[str] = []
    for legacy_path, target_path in write_redirects.collect_legacy_redirects(
        catalog,
        output_root=site_root,
    ):
        rel_legacy = legacy_path.relative_to(site_root).as_posix()
        if not legacy_path.is_file():
            errors.append(f"missing legacy redirect page: {rel_legacy}")
            continue
        if write_redirects.REDIRECT_MARKER not in legacy_path.read_text(encoding="utf-8"):
            errors.append(f"legacy route is not a generated redirect: {rel_legacy}")
            continue
        if not target_path.is_file():
            rel_target = target_path.relative_to(site_root).as_posix()
            errors.append(f"legacy redirect target missing: {rel_legacy} -> {rel_target}")
    return errors


def check_forbidden_artifacts(site_root: Path) -> list[str]:
    errors: list[str] = []
    published = assert_private_content.check_site(site_root)
    for path in published:
        errors.append(f"forbidden artifact published: {path.relative_to(site_root).as_posix()}")

    for name in FORBIDDEN_PUBLISHED_NAMES:
        for path in site_root.rglob(name):
            if path.is_file():
                errors.append(
                    f"forbidden planning file published: {path.relative_to(site_root).as_posix()}"
                )
    return errors


def expected_colab_urls(catalog: content_model.ContentCatalog) -> list[str]:
    if not catalog.course.colab.enabled:
        return []

    repo = catalog.course.repo
    urls: list[str] = []
    for lecture in catalog.lectures:
        notebook_path = (
            f"{content_model.LECTURES_URL_PREFIX}/{lecture.slug}/{lecture.surfaces.learn}"
        )
        urls.append(
            colab.notebook_url(
                owner=repo.owner,
                name=repo.name,
                branch=repo.branch,
                repo_relative_path=notebook_path,
            )
        )
    for assignment in catalog.assignments:
        notebook_path = (
            f"{content_model.ASSIGNMENTS_URL_PREFIX}/{assignment.slug}/"
            f"{assignment.notebook}"
        )
        urls.append(
            colab.notebook_url(
                owner=repo.owner,
                name=repo.name,
                branch=repo.branch,
                repo_relative_path=notebook_path,
            )
        )
    return urls


def check_colab_links(site_root: Path, catalog: content_model.ContentCatalog) -> list[str]:
    if not catalog.course.colab.enabled:
        return []

    expected = expected_colab_urls(catalog)
    if not expected:
        return ["Colab enabled but no notebook URLs were generated from the catalog"]

    found: set[str] = set()
    for html_path in site_root.rglob("*.html"):
        found.update(COLAB_URL_PATTERN.findall(html_path.read_text(encoding="utf-8")))

    if not found:
        return ["no Colab notebook URLs found in rendered HTML"]

    if not found:
        return ["no Colab notebook URLs found in rendered HTML"]

    if not any(url in found for url in expected):
        return ["no expected Colab notebook URLs found in rendered HTML"]
    return []


def check_gallery_hrefs(site_root: Path) -> list[str]:
    gallery_path = content_model.SITE_ROOT / "generated" / "gallery.json"
    if not gallery_path.is_file():
        return ["generated/gallery.json is missing (run build_interactives.py first)"]

    errors: list[str] = []
    for entry in gallery.load_gallery_json(gallery_path):
        if entry.source_kind == "standalone":
            target = site_root / entry.href.strip("/") / "index.html"
        else:
            target = site_root / entry.href.strip("/") / "index.html"
        if not target.is_file():
            errors.append(
                f"gallery entry {entry.id!r} missing rendered target: "
                f"{target.relative_to(site_root).as_posix()}"
            )
    return errors


def check_local_site(site_root: Path | None = None) -> list[str]:
    site_root = site_root or content_model.SITE_ROOT / "_site"
    if not site_root.is_dir():
        return [f"built site not found: {site_root}"]

    catalog = content_model.load_catalog()
    routes = required_routes(catalog)
    errors: list[str] = []
    errors.extend(check_required_routes_local(site_root, routes))
    errors.extend(check_legacy_redirects_local(catalog, site_root))
    errors.extend(check_forbidden_artifacts(site_root))
    errors.extend(check_colab_links(site_root, catalog))
    errors.extend(check_gallery_hrefs(site_root))
    errors.extend(check_internal_links(site_root))
    return errors


def check_remote_routes(base_url: str, routes: Iterable[str]) -> list[str]:
    errors: list[str] = []
    base = base_url.rstrip("/") + "/"
    for route in routes:
        url = urljoin(base, route)
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if response.status >= 400:
                    errors.append(f"{url}: HTTP {response.status}")
        except urllib.error.HTTPError as error:
            errors.append(f"{url}: HTTP {error.code}")
        except Exception as error:  # noqa: BLE001 - aggregate remote failures
            errors.append(f"{url}: {error}")
    return errors


def check_remote_legacy_redirects(
    base_url: str,
    catalog: content_model.ContentCatalog,
) -> list[str]:
    errors: list[str] = []
    base = base_url.rstrip("/") + "/"
    for legacy_path, target_path in write_redirects.collect_legacy_redirects(
        catalog,
        output_root=content_model.SITE_ROOT / "_site",
    ):
        rel_legacy = legacy_path.relative_to(content_model.SITE_ROOT / "_site").as_posix()
        rel_target = target_path.relative_to(content_model.SITE_ROOT / "_site").as_posix()
        url = urljoin(base, rel_legacy)
        request = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
        except Exception as error:  # noqa: BLE001
            errors.append(f"{url}: {error}")
            continue
        if write_redirects.REDIRECT_MARKER not in body:
            errors.append(f"{url}: response is not a generated legacy redirect")
            continue
        if rel_target not in body and Path(rel_target).name not in body:
            errors.append(f"{url}: redirect body does not reference {rel_target}")
    return errors


def check_remote_colab_presence(base_url: str) -> list[str]:
    assignments_url = urljoin(base_url.rstrip("/") + "/", "assignments.html")
    request = urllib.request.Request(assignments_url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8", errors="replace")
    except Exception as error:  # noqa: BLE001
        return [f"{assignments_url}: {error}"]

    if not COLAB_URL_PATTERN.search(body):
        return [f"{assignments_url}: no Colab notebook URLs found"]
    return []


def check_deployed_site(base_url: str) -> list[str]:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return [f"invalid base URL: {base_url!r}"]

    catalog = content_model.load_catalog()
    routes = required_routes(catalog)
    errors: list[str] = []
    errors.extend(check_remote_routes(base_url, routes))
    errors.extend(check_remote_legacy_redirects(base_url, catalog))
    errors.extend(check_remote_colab_presence(base_url))
    return errors


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-root",
        type=Path,
        default=content_model.SITE_ROOT / "_site",
        help="rendered site directory for local checks (default: _site/)",
    )
    parser.add_argument(
        "--base-url",
        help="when set, verify the deployed site at this GitHub Pages base URL",
    )
    args = parser.parse_args(argv)

    if args.base_url:
        errors = check_deployed_site(args.base_url)
    else:
        errors = check_local_site(args.site_root)

    if errors:
        print("Site verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        raise SystemExit(1)

    if args.base_url:
        print(f"Deployed site verification passed for {args.base_url.rstrip('/')}.")
    else:
        print(f"Local site verification passed for {args.site_root}.")


if __name__ == "__main__":
    main()
