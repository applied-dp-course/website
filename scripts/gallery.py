"""Build and validate the interactive tools gallery catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import content_model


class GalleryError(ValueError):
    """Raised when gallery metadata is invalid."""


@dataclass(frozen=True)
class GalleryEntry:
    id: str
    title: str
    summary: str
    source_kind: str
    source_title: str
    source_lecture_number: str | None
    subjects: tuple[str, ...]
    runtime: str
    href: str


def _lecture_app_href(slug: str, app_path: str) -> str:
    normalized = app_path.replace("\\", "/").strip("/")
    return f"{content_model.LECTURES_URL_PREFIX}/{slug}/{normalized}/"


def _standalone_tool_href(slug: str) -> str:
    return f"tools/{slug}/"


def build_gallery_entries(catalog: content_model.ContentCatalog) -> tuple[GalleryEntry, ...]:
    entries: list[GalleryEntry] = []

    for lecture in catalog.lectures:
        for app in lecture.apps:
            if not app.gallery:
                continue
            entries.append(
                GalleryEntry(
                    id=app.id,
                    title=app.title,
                    summary="",
                    source_kind="lecture",
                    source_title=lecture.title,
                    source_lecture_number=lecture.number,
                    subjects=lecture.subjects,
                    runtime=app.runtime,
                    href=_lecture_app_href(lecture.slug, app.path),
                )
            )

    for tool in catalog.tools:
        if not tool.gallery:
            continue
        entries.append(
            GalleryEntry(
                id=tool.slug,
                title=tool.title,
                summary=tool.summary,
                source_kind="standalone",
                source_title=tool.title,
                source_lecture_number=None,
                subjects=tool.subjects,
                runtime=tool.runtime,
                href=_standalone_tool_href(tool.slug),
            )
        )

    entries.sort(key=lambda entry: (entry.title.casefold(), entry.id))
    validate_unique_ids(entries)
    return tuple(entries)


def validate_unique_ids(entries: tuple[GalleryEntry, ...] | list[GalleryEntry]) -> None:
    seen: dict[str, GalleryEntry] = {}
    for entry in entries:
        if entry.id in seen:
            previous = seen[entry.id]
            raise GalleryError(
                f"duplicate gallery id {entry.id!r}: "
                f"{previous.href} conflicts with {entry.href}"
            )
        seen[entry.id] = entry


def validate_entrypoints_exist(
    entries: tuple[GalleryEntry, ...],
    site_root: Path,
) -> None:
    missing: list[str] = []
    for entry in entries:
        if entry.source_kind == "standalone":
            entrypoint = site_root / "tools" / entry.id / "index.qmd"
            if not entrypoint.is_file():
                missing.append(f"{entry.id}: missing {entrypoint.relative_to(site_root).as_posix()}")
            continue

        app_index = site_root / entry.href.strip("/") / "index.html"
        if not app_index.is_file():
            missing.append(
                f"{entry.id}: missing {app_index.relative_to(site_root).as_posix()}"
            )

    if missing:
        raise GalleryError(
            "gallery entrypoint(s) missing:\n" + "\n".join(f"- {item}" for item in missing)
        )


def entry_to_dict(entry: GalleryEntry) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": entry.id,
        "title": entry.title,
        "summary": entry.summary,
        "source_kind": entry.source_kind,
        "source_title": entry.source_title,
        "subjects": list(entry.subjects),
        "runtime": entry.runtime,
        "href": entry.href,
    }
    if entry.source_lecture_number is not None:
        payload["source_lecture_number"] = entry.source_lecture_number
    return payload


def gallery_to_dict(entries: tuple[GalleryEntry, ...]) -> dict[str, object]:
    return {"entries": [entry_to_dict(entry) for entry in entries]}


def write_gallery_json(
    entries: tuple[GalleryEntry, ...],
    destination: Path,
    *,
    site_root: Path | None = None,
) -> Path:
    site_root = site_root or content_model.SITE_ROOT
    validate_entrypoints_exist(entries, site_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(gallery_to_dict(entries), indent=2, sort_keys=True) + "\n"
    destination.write_text(serialized, encoding="utf-8")
    return destination


def load_gallery_json(source: Path | None = None) -> tuple[GalleryEntry, ...]:
    source = source or content_model.SITE_ROOT / "generated" / "gallery.json"
    if not source.exists():
        raise GalleryError(f"gallery file does not exist: {source}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        raise GalleryError(f"{source}: expected top-level 'entries' list")

    entries: list[GalleryEntry] = []
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise GalleryError(f"{source}: entries[{index}] must be a mapping")
        lecture_number = raw.get("source_lecture_number")
        entries.append(
            GalleryEntry(
                id=str(raw["id"]),
                title=str(raw["title"]),
                summary=str(raw.get("summary") or ""),
                source_kind=str(raw["source_kind"]),
                source_title=str(raw["source_title"]),
                source_lecture_number=(
                    str(lecture_number) if lecture_number is not None else None
                ),
                subjects=tuple(raw.get("subjects") or ()),
                runtime=str(raw["runtime"]),
                href=str(raw["href"]),
            )
        )
    return tuple(entries)
