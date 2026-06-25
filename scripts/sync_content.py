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


def _item_link(
    item: content_model.ContentItem,
    label: str | None = None,
    *,
    rendered: bool = True,
) -> str:
    path = _rendered_public_path(item) if rendered else item.public_path
    return f"[{escape_markdown_table_cell(label or item.title)}](../{path})"


def _app_link(app: content_model.ContentApp) -> str:
    return f"[{escape_markdown_table_cell(app.title)}](../{app.path.strip('/')}/)"


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


def _schedule_table_rows(
    schedule: content_model.OfferingSchedule,
    catalog: content_model.ContentCatalog,
    *,
    include_colab: bool,
) -> list[str]:
    collections = {
        "blog_post": {item.name: item for item in catalog.blog_posts},
        "lecture_presentation": {
            item.name: item for item in catalog.lecture_presentations
        },
        "class_assignment": {item.name: item for item in catalog.class_assignments},
        "home_assignment": {item.name: item for item in catalog.home_assignments},
    }
    rows = [
        "| Week | Date | Topic | Blog post | Slides | Class assignment | Home assignment | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
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
            link = _item_link(item)
            if include_colab and item.entrypoint.endswith(".ipynb"):
                link = _append_colab(link, catalog, item)
            cells.append(link)
        rows.append(
            "| "
            + " | ".join(
                [
                    escape_markdown_table_cell(row.week),
                    _format_date(row),
                    escape_markdown_table_cell(row.topic) if row.topic else EM_DASH,
                    *cells,
                    escape_markdown_table_cell(row.notes) if row.notes else EM_DASH,
                ]
            )
            + " |"
        )
    return rows


def render_schedule_page(catalog: content_model.ContentCatalog) -> str:
    schedule = content_model.current_offering_schedule(catalog)
    if not schedule.rows:
        return f"_The {schedule.offering.label} schedule has no weeks yet._"
    return "\n".join(_schedule_table_rows(schedule, catalog, include_colab=True))


def _group_by_subject(
    items: tuple[content_model.ContentItem, ...],
) -> dict[str, list[content_model.ContentItem]]:
    grouped: dict[str, list[content_model.ContentItem]] = defaultdict(list)
    for item in items:
        for subject in item.subjects or ("Other topics",):
            grouped[subject].append(item)
    for entries in grouped.values():
        entries.sort(key=lambda item: (item.title.casefold(), item.name))
    return dict(sorted(grouped.items(), key=lambda pair: pair[0].casefold()))


def _render_content_collection(
    heading: str,
    items: tuple[content_model.ContentItem, ...],
    catalog: content_model.ContentCatalog,
) -> str:
    if not items:
        return f"## {heading}\n\n_No {heading.casefold()} are published yet._"
    sections = [f"## {heading}"]
    for subject, subject_items in _group_by_subject(items).items():
        entries: list[str] = []
        for item in subject_items:
            link = _item_link(item)
            if item.entrypoint.endswith(".ipynb"):
                link = _append_colab(link, catalog, item)
            apps = ""
            if item.apps:
                apps = " · apps: " + ", ".join(_app_link(app) for app in item.apps)
            entries.append(f"- **{escape_markdown_table_cell(item.title)}** — {link}{apps}")
        sections.append(f"### {escape_markdown_table_cell(subject)}\n\n" + "\n".join(entries))
    return "\n\n".join(sections)


def render_lectures_page(catalog: content_model.ContentCatalog) -> str:
    return "\n\n".join(
        [
            _render_content_collection(
                "Lecture presentations",
                catalog.lecture_presentations,
                catalog,
            ),
            _render_content_collection("Blog posts", catalog.blog_posts, catalog),
        ]
    )


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


def _format_due(values: list[tuple[str, date | None]]) -> str:
    if not values:
        return EM_DASH
    return "; ".join(
        f"Week {week}" + (f" ({due_date.isoformat()})" if due_date else "")
        for week, due_date in values
    )


def _render_assignments(
    heading: str,
    items: tuple[content_model.ContentItem, ...],
    due_field: str,
    catalog: content_model.ContentCatalog,
) -> str:
    if not items:
        return f"## {heading}\n\n_No {heading.casefold()} are published yet._"
    due_map = _assignment_due_map(catalog, due_field)
    lines = [f"## {heading}", ""]
    for item in items:
        link = _append_colab(_item_link(item, "notebook"), catalog, item)
        estimated = item.estimated_time or EM_DASH
        related = ", ".join(item.related) if item.related else EM_DASH
        lines.append(
            f"- **{escape_markdown_table_cell(item.title)}** — {link} · "
            f"due {_format_due(due_map.get(item.name, []))} · "
            f"est. {escape_markdown_table_cell(estimated)} · related: {related}"
        )
    return "\n".join(lines)


def render_assignments_page(catalog: content_model.ContentCatalog) -> str:
    return "\n\n".join(
        [
            _render_assignments(
                "Class assignments",
                catalog.class_assignments,
                "class_assignment",
                catalog,
            ),
            _render_assignments(
                "Home assignments",
                catalog.home_assignments,
                "home_assignment",
                catalog,
            ),
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
        ("schedule.qmd", render_schedule_page(catalog), SCHEDULE_SECTION),
        ("archive.qmd", render_archive_page(catalog), ARCHIVE_SECTION),
        ("index.qmd", render_offering_banner(catalog), OFFERING_BANNER_SECTION),
        ("assignments.qmd", render_assignments_page(catalog), ASSIGNMENTS_SECTION),
        ("syllabus.qmd", render_syllabus_logistics(catalog), SYLLABUS_LOGISTICS_SECTION),
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
