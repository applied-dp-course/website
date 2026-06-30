#!/usr/bin/env python3
"""Refresh generated sections in site pages from validated authored content."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import colab
import content_model
import gallery


MARKER_PREFIX = "<!-- BEGIN AUTO-GENERATED"
MARKER_SUFFIX = "-->"
EM_DASH = "—"


@dataclass(frozen=True)
class GeneratedSection:
    name: str

    @property
    def begin(self) -> str:
        return f"{MARKER_PREFIX} {self.name} {MARKER_SUFFIX}"

    @property
    def end(self) -> str:
        return f"<!-- END AUTO-GENERATED {self.name} {MARKER_SUFFIX}"


LECTURES_SECTION = GeneratedSection("LECTURES")
SCHEDULE_SECTION = GeneratedSection("SCHEDULE")
ARCHIVE_SECTION = GeneratedSection("ARCHIVE")
ASSIGNMENTS_SECTION = GeneratedSection("ASSIGNMENTS")
CLASS_ASSIGNMENTS_SECTION = GeneratedSection("CLASS ASSIGNMENTS")
HOME_ASSIGNMENTS_SECTION = GeneratedSection("HOME ASSIGNMENTS")
TOOLS_SECTION = GeneratedSection("TOOLS")
OFFERING_BANNER_SECTION = GeneratedSection("OFFERING BANNER")
SYLLABUS_LOGISTICS_SECTION = GeneratedSection("SYLLABUS LOGISTICS")


def _page_path(name: str) -> Path:
    path = content_model.PAGES_DIR / name
    if path.exists() or content_model.PAGES_DIR.is_dir():
        return path
    return content_model.SITE_ROOT / name


def replace_generated_section(path: Path, body: str, section: GeneratedSection) -> None:
    if not path.exists():
        raise RuntimeError(f"{path.relative_to(content_model.SITE_ROOT)} does not exist")
    source = path.read_text(encoding="utf-8")
    begin_count = source.count(section.begin)
    end_count = source.count(section.end)
    if begin_count != 1 or end_count != 1:
        raise RuntimeError(
            f"{path.relative_to(content_model.SITE_ROOT)} must contain exactly one "
            f"{section.name} generated-section marker pair "
            f"(found {begin_count} begin, {end_count} end)"
        )
    replacement = f"{section.begin}\n{body.rstrip()}\n{section.end}"
    pattern = re.compile(
        rf"{re.escape(section.begin)}.*?{re.escape(section.end)}",
        re.DOTALL,
    )
    path.write_text(pattern.sub(replacement, source), encoding="utf-8")


def escape_markdown_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _rendered_public_path(item: content_model.ContentItem) -> str:
    path = Path(item.public_path)
    if path.suffix in {".ipynb", ".qmd"}:
        return path.with_suffix(".html").as_posix()
    return path.as_posix()


def _content_link_prefix(page_name: str) -> str:
    """Return a relative prefix from a page under ``pages/`` to site-root content paths."""

    depth = len(Path(page_name).parts)
    return "../" * depth


def _item_link(
    item: content_model.ContentItem,
    label: str | None = None,
    *,
    rendered: bool = True,
    prefix: str = "../",
) -> str:
    path = _rendered_public_path(item) if rendered else item.public_path
    return f"[{escape_markdown_table_cell(label or item.title)}]({prefix}{path})"


def _app_link(app: content_model.ContentApp, *, prefix: str = "../") -> str:
    return f"[{escape_markdown_table_cell(app.title)}]({prefix}{app.path.strip('/')}/)"


def _colab_badge(catalog: content_model.ContentCatalog, item: content_model.ContentItem) -> str:
    course = catalog.course
    return colab.badge_for_notebook(
        enabled=course.colab.enabled,
        owner=course.repo.owner,
        name=course.repo.name,
        branch=course.repo.branch,
        repo_relative_path=item.public_path,
    )


def _append_colab(text: str, catalog: content_model.ContentCatalog, item: content_model.ContentItem) -> str:
    badge = _colab_badge(catalog, item)
    return f"{text} · {badge}" if badge else text


def _format_date(row: content_model.ScheduleRow) -> str:
    return row.date.isoformat() if row.date else EM_DASH


def _format_due(values: list[tuple[str, date | None]], *, include_dates: bool = False) -> str:
    if not values:
        return EM_DASH
    return "; ".join(
        f"Week {week}" + (f" ({due_date.isoformat()})" if include_dates and due_date else "")
        for week, due_date in values
    )


def _schedule_table_rows(
    schedule: content_model.OfferingSchedule,
    catalog: content_model.ContentCatalog,
    *,
    include_colab: bool,
    include_dates: bool = True,
    link_prefix: str = "../",
) -> list[str]:
    collections = {
        "blog_post": {item.name: item for item in catalog.blog_posts},
        "lecture_presentation": {
            item.name: item for item in catalog.lecture_presentations
        },
        "class_assignment": {item.name: item for item in catalog.class_assignments},
        "home_assignment": {item.name: item for item in catalog.home_assignments},
    }
    header = (
        "| Week | Date | Topic | Blog post | Slides | Class assignment | Home assignment | Notes |"
        if include_dates
        else "| Week | Topic | Blog post | Slides | Class assignment | Home assignment | Notes |"
    )
    column_count = header.count("|") - 1
    separator = "|" + "|".join(["---"] * column_count) + "|"
    rows = [header, separator]
    for row in schedule.rows:
        cells: list[str] = []
        for field in (
            "blog_post",
            "lecture_presentation",
            "class_assignment",
            "home_assignment",
        ):
            name = getattr(row, field)
            item = collections[field].get(name) if name else None
            if item is None:
                cells.append(EM_DASH)
                continue
            link = _item_link(item, prefix=link_prefix)
            if include_colab and item.entrypoint.endswith(".ipynb"):
                link = _append_colab(link, catalog, item)
            cells.append(link)
        leading = [
            escape_markdown_table_cell(row.week),
            *([_format_date(row)] if include_dates else []),
            escape_markdown_table_cell(row.topic) if row.topic else EM_DASH,
        ]
        rows.append(
            "| "
            + " | ".join(
                [
                    *leading,
                    *cells,
                    escape_markdown_table_cell(row.notes) if row.notes else EM_DASH,
                ]
            )
            + " |"
        )
    return rows


def render_syllabus_page(catalog: content_model.ContentCatalog) -> str:
    schedule = content_model.current_offering_schedule(catalog)
    if not schedule.rows:
        return f"_The {schedule.offering.label} syllabus has no weeks yet._"
    return "\n".join(
        _schedule_table_rows(
            schedule,
            catalog,
            include_colab=True,
            include_dates=False,
            link_prefix=_content_link_prefix("syllabus.qmd"),
        )
    )


def render_schedule_page(catalog: content_model.ContentCatalog) -> str:
    """Legacy alias kept for tests that expect the full dated schedule table."""

    schedule = content_model.current_offering_schedule(catalog)
    if not schedule.rows:
        return f"_The {schedule.offering.label} schedule has no weeks yet._"
    return "\n".join(
        _schedule_table_rows(
            schedule,
            catalog,
            include_colab=True,
            include_dates=True,
            link_prefix="../",
        )
    )


def _lecture_bundles(
    catalog: content_model.ContentCatalog,
) -> dict[str, dict[str, content_model.ContentItem]]:
    bundles: dict[str, dict[str, content_model.ContentItem]] = defaultdict(dict)
    for item in catalog.blog_posts:
        bundles[item.name]["blog_post"] = item
    for item in catalog.lecture_presentations:
        bundles[item.name]["lecture_presentation"] = item
    return bundles


def _lecture_title(bundle: dict[str, content_model.ContentItem]) -> str:
    for key in ("blog_post", "lecture_presentation"):
        if key in bundle:
            return bundle[key].title
    return "Untitled lecture"


def _lecture_slug(row: content_model.ScheduleRow) -> str | None:
    return row.lecture_presentation or row.blog_post


def _items_in_schedule_order(
    items: tuple[content_model.ContentItem, ...],
    schedule: content_model.OfferingSchedule,
    field: str,
) -> list[content_model.ContentItem]:
    by_name = {item.name: item for item in items}
    ordered: list[content_model.ContentItem] = []
    seen: set[str] = set()
    for row in schedule.rows:
        name = getattr(row, field)
        if not name or name in seen:
            continue
        item = by_name.get(name)
        if item is None:
            continue
        ordered.append(item)
        seen.add(name)
    for item in items:
        if item.name not in seen:
            ordered.append(item)
    return ordered


def render_lectures_page(catalog: content_model.ContentCatalog) -> str:
    schedule = content_model.current_offering_schedule(catalog)
    bundles = _lecture_bundles(catalog)
    if not schedule.rows and not bundles:
        return "_No lectures are published yet._"
    sections: list[str] = []
    rendered_slugs: set[str] = set()
    for row in schedule.rows:
        slug = _lecture_slug(row)
        if slug:
            if slug in rendered_slugs:
                continue
            rendered_slugs.add(slug)
            bundle = bundles.get(slug, {})
            title = _lecture_title(bundle) if bundle else (row.topic or slug)
        elif not row.topic:
            continue
        else:
            title = row.topic
            bundle = {}
        lines = [
            f"## {escape_markdown_table_cell(title)}",
            "",
            f"_Week {escape_markdown_table_cell(row.week)}_",
            "",
            "_Short introduction coming soon._",
            "",
        ]
        blog = bundle.get("blog_post")
        if blog is not None:
            link = _append_colab(_item_link(blog, "Blog post"), catalog, blog)
            lines.append(f"- **Blog post** — {link}")
        presentation = bundle.get("lecture_presentation")
        if presentation is not None:
            link = _item_link(presentation, "Presentation")
            lines.append(f"- **Presentation** — {link}")
        sections.append("\n".join(lines))
    for slug in sorted(bundles, key=lambda name: _lecture_title(bundles[name]).casefold()):
        if slug in rendered_slugs:
            continue
        bundle = bundles[slug]
        title = _lecture_title(bundle)
        lines = [
            f"## {escape_markdown_table_cell(title)}",
            "",
            "_Short introduction coming soon._",
            "",
        ]
        blog = bundle.get("blog_post")
        if blog is not None:
            link = _append_colab(_item_link(blog, "Blog post"), catalog, blog)
            lines.append(f"- **Blog post** — {link}")
        presentation = bundle.get("lecture_presentation")
        if presentation is not None:
            link = _item_link(presentation, "Presentation")
            lines.append(f"- **Presentation** — {link}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else "_No lectures are published yet._"


def _assignment_due_map(
    catalog: content_model.ContentCatalog,
    field: str,
) -> dict[str, list[tuple[str, date | None]]]:
    due: dict[str, list[tuple[str, date | None]]] = defaultdict(list)
    for row in content_model.current_offering_schedule(catalog).rows:
        name = getattr(row, field)
        if name:
            due[name].append((row.week, row.date))
    return due


def _related_lecture_links(
    catalog: content_model.ContentCatalog,
    related: tuple[str, ...],
) -> str:
    if not related:
        return EM_DASH
    presentations = {item.name: item for item in catalog.lecture_presentations}
    blog_posts = {item.name: item for item in catalog.blog_posts}
    links: list[str] = []
    for name in related:
        item = presentations.get(name) or blog_posts.get(name)
        if item is None:
            links.append(escape_markdown_table_cell(name))
            continue
        links.append(_item_link(item, item.title))
    return ", ".join(links)


def _render_assignments(
    heading: str,
    items: tuple[content_model.ContentItem, ...],
    due_field: str,
    catalog: content_model.ContentCatalog,
    *,
    detailed: bool,
) -> str:
    if not items:
        return f"## {heading}\n\n_No {heading.casefold()} are published yet._"
    schedule = content_model.current_offering_schedule(catalog)
    due_map = _assignment_due_map(catalog, due_field)
    ordered_items = _items_in_schedule_order(items, schedule, due_field)
    lines = [f"## {heading}", ""]
    for item in ordered_items:
        link = _append_colab(_item_link(item, "notebook"), catalog, item)
        estimated = item.estimated_time or EM_DASH
        if detailed:
            lines.extend(
                [
                    f"### {escape_markdown_table_cell(item.title)}",
                    "",
                    "_Assignment explanation coming soon._",
                    "",
                    f"- **Related lecture:** {_related_lecture_links(catalog, item.related)}",
                    f"- **Notebook** — {link}",
                    f"- **Due:** {_format_due(due_map.get(item.name, []))}",
                    f"- **Estimated time:** {escape_markdown_table_cell(estimated)}",
                    "",
                ]
            )
            continue
        related = ", ".join(item.related) if item.related else EM_DASH
        lines.append(
            f"- **{escape_markdown_table_cell(item.title)}** — {link} · "
            f"due {_format_due(due_map.get(item.name, []))} · "
            f"est. {escape_markdown_table_cell(estimated)} · related: {related}"
        )
    return "\n".join(lines).rstrip()


def render_class_assignments_page(catalog: content_model.ContentCatalog) -> str:
    return _render_assignments(
        "Class assignments",
        catalog.class_assignments,
        "class_assignment",
        catalog,
        detailed=True,
    )


def render_home_assignments_page(catalog: content_model.ContentCatalog) -> str:
    return _render_assignments(
        "Home assignments",
        catalog.home_assignments,
        "home_assignment",
        catalog,
        detailed=True,
    )


def render_assignments_page(catalog: content_model.ContentCatalog) -> str:
    return "\n\n".join(
        [
            render_class_assignments_page(catalog),
            render_home_assignments_page(catalog),
        ]
    )


def render_archive_page(catalog: content_model.ContentCatalog) -> str:
    blocks: list[str] = []
    for offering_schedule in catalog.offerings:
        offering = offering_schedule.offering
        summary = html.escape(offering.label)
        if offering.start_date and offering.end_date:
            summary += f" ({offering.start_date.isoformat()} – {offering.end_date.isoformat()})"
        if offering.term == catalog.course.current_offering:
            summary += " — current"
        body = (
            "\n".join(
                _schedule_table_rows(
                    offering_schedule,
                    catalog,
                    include_colab=offering.term == catalog.course.current_offering,
                )
            )
            if offering_schedule.rows
            else f"_The {offering.label} schedule has no weeks yet._"
        )
        blocks.append(
            "\n".join(
                ["<details>", f"<summary><strong>{summary}</strong></summary>", "", body, "", "</details>"]
            )
        )
    return "\n\n".join(blocks) if blocks else "_No offerings are configured yet._"


def render_offering_banner(catalog: content_model.ContentCatalog) -> str:
    offering = content_model.current_offering_schedule(catalog).offering
    lines = [f"**{escape_markdown_table_cell(offering.label)}**", ""]
    if offering.start_date and offering.end_date:
        lines.append(f"- **Dates:** {offering.start_date.isoformat()} – {offering.end_date.isoformat()}")
    meeting = [part for part in (offering.meeting.time, offering.meeting.place) if part]
    if meeting:
        lines.append(f"- **Meeting:** {' · '.join(meeting)}")
    if catalog.course.instructors:
        instructors = [
            f"[{item.name}]({item.url})" if item.url else item.name
            for item in catalog.course.instructors
        ]
        lines.append(f"- **Instructor(s):** {', '.join(instructors)}")
    return "\n".join(lines)


def _render_person(person: dict[str, object]) -> str | None:
    name = str(person.get("name") or "").strip()
    if not name:
        return None
    url = str(person.get("url") or "").strip()
    role = str(person.get("role") or "").strip()
    label = f"[{name}]({url})" if url else name
    return f"- {label}" + (f" — {role}" if role else "")


def render_syllabus_logistics(catalog: content_model.ContentCatalog) -> str:
    offering = content_model.current_offering_schedule(catalog).offering
    lines = [f"### {offering.label}", ""]
    if offering.start_date and offering.end_date:
        lines.append(f"- **Dates:** {offering.start_date.isoformat()} – {offering.end_date.isoformat()}")
    meeting = [part for part in (offering.meeting.time, offering.meeting.place) if part]
    if meeting:
        lines.append(f"- **Meeting:** {' · '.join(meeting)}")
    if catalog.course.instructors:
        lines.append(
            "- **Instructor(s):** "
            + ", ".join(
                f"[{item.name}]({item.url})" if item.url else item.name
                for item in catalog.course.instructors
            )
        )
    staff = [entry for person in offering.staff if (entry := _render_person(person))]
    if staff:
        lines.extend(["", "#### Staff", "", *staff])
    if offering.grading_notes:
        lines.extend(["", "#### Grading notes (this term)", "", offering.grading_notes])
    return "\n".join(lines)


def _tools_by_subject(
    entries: tuple[gallery.GalleryEntry, ...],
) -> dict[str, list[gallery.GalleryEntry]]:
    grouped: dict[str, list[gallery.GalleryEntry]] = defaultdict(list)
    for entry in entries:
        for subject in entry.subjects or ("Other topics",):
            grouped[subject].append(entry)
    return dict(sorted(grouped.items(), key=lambda pair: pair[0].casefold()))


def render_tools_page(entries: tuple[gallery.GalleryEntry, ...]) -> str:
    if not entries:
        return "_No interactive tools are published in the gallery yet._"
    sections: list[str] = []
    for subject, subject_entries in _tools_by_subject(entries).items():
        cards = []
        for entry in sorted(subject_entries, key=lambda item: item.title.casefold()):
            provenance = "standalone" if entry.source_kind == "standalone" else f"from {entry.source_title}"
            summary = f" — {entry.summary}" if entry.summary else ""
            cards.append(f"- **[{entry.title}](../{entry.href})** — {provenance}{summary}")
        sections.append(f"### {subject}\n\n" + "\n".join(cards))
    return "\n\n".join(sections)


def _relative(path: Path) -> str:
    return path.relative_to(content_model.SITE_ROOT).as_posix()


def _item_json(item: content_model.ContentItem) -> dict[str, object]:
    return {
        "name": item.name,
        "title": item.title,
        "entrypoint": item.entrypoint,
        "subjects": list(item.subjects),
        "status": item.status,
        "estimated_time": item.estimated_time,
        "related": list(item.related),
        "source_path": _relative(item.source_path),
    }


def catalog_to_dict(catalog: content_model.ContentCatalog) -> dict[str, object]:
    return {
        "course": {
            "title": catalog.course.title,
            "current_offering": catalog.course.current_offering,
        },
        "lecture_presentations": [_item_json(item) for item in catalog.lecture_presentations],
        "blog_posts": [_item_json(item) for item in catalog.blog_posts],
        "class_assignments": [_item_json(item) for item in catalog.class_assignments],
        "home_assignments": [_item_json(item) for item in catalog.home_assignments],
        "offerings": [
            {
                "term": schedule.offering.term,
                "label": schedule.offering.label,
                "schedule": [
                    {
                        "week": row.week,
                        "date": row.date.isoformat() if row.date else None,
                        "topic": row.topic,
                        "blog_post": row.blog_post,
                        "lecture_presentation": row.lecture_presentation,
                        "class_assignment": row.class_assignment,
                        "home_assignment": row.home_assignment,
                        "notes": row.notes,
                    }
                    for row in schedule.rows
                ],
            }
            for schedule in catalog.offerings
        ],
    }


def write_catalog_json(
    catalog: content_model.ContentCatalog,
    destination: Path | None = None,
) -> Path:
    destination = destination or content_model.GENERATED_DIR / "catalog.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(catalog_to_dict(catalog), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def sync_catalog_pages(
    catalog: content_model.ContentCatalog | None = None,
) -> content_model.ContentCatalog:
    catalog = catalog or content_model.load_catalog()
    for name, body, section in (
        ("lectures.qmd", render_lectures_page(catalog), LECTURES_SECTION),
        ("syllabus.qmd", render_syllabus_page(catalog), SCHEDULE_SECTION),
        ("archive.qmd", render_archive_page(catalog), ARCHIVE_SECTION),
        ("index.qmd", render_offering_banner(catalog), OFFERING_BANNER_SECTION),
        ("course.qmd", render_offering_banner(catalog), OFFERING_BANNER_SECTION),
        ("course.qmd", render_syllabus_logistics(catalog), SYLLABUS_LOGISTICS_SECTION),
        ("class-assignments.qmd", render_class_assignments_page(catalog), CLASS_ASSIGNMENTS_SECTION),
        ("home-assignments.qmd", render_home_assignments_page(catalog), HOME_ASSIGNMENTS_SECTION),
    ):
        path = _page_path(name)
        if path.exists():
            replace_generated_section(path, body, section)
    write_catalog_json(catalog)
    return catalog


def sync_gallery_pages() -> None:
    gallery_path = content_model.GENERATED_DIR / "gallery.json"
    if not gallery_path.exists():
        raise RuntimeError("_generated/gallery.json not found; run build_interactives.py first")
    replace_generated_section(
        _page_path("tools.qmd"),
        render_tools_page(gallery.load_gallery_json(gallery_path)),
        TOOLS_SECTION,
    )


def normalize_lecture_sources(lectures_dir: Path | None = None) -> int:
    """Legacy API: source normalization was removed because content is author-owned."""
    del lectures_dir
    return 0


def run_phase(phase: str) -> None:
    if phase == "catalog":
        catalog = sync_catalog_pages()
        print(
            "Synchronized catalog without modifying content sources: "
            f"{len(catalog.lecture_presentations)} presentation(s), "
            f"{len(catalog.blog_posts)} blog post(s), "
            f"{len(catalog.assignments)} assignment(s)."
        )
        return
    if phase == "gallery":
        sync_gallery_pages()
        print(f"Gallery phase complete: {len(gallery.load_gallery_json())} tool(s) published.")
        return
    raise SystemExit(f"unknown sync phase: {phase}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("catalog", "gallery"), default="catalog")
    args = parser.parse_args(argv)
    run_phase(args.phase)


if __name__ == "__main__":
    main()
