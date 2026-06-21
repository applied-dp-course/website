"""Course catalog metadata: load, validate, and normalize content configuration."""

from __future__ import annotations

import csv
import re
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


SITE_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = SITE_ROOT / "content"
LECTURES_DIR = CONTENT_DIR / "lectures"
LECTURES_URL_PREFIX = "content/lectures"
ASSIGNMENTS_URL_PREFIX = "content/assignments"
ASSIGNMENTS_DIR = CONTENT_DIR / "assignments"
OFFERINGS_DIR = CONTENT_DIR / "offerings"
TOOLS_DIR = SITE_ROOT / "tools"

COURSE_REQUIRED_KEYS = {"title", "repo", "current_offering", "colab"}
OFFERING_REQUIRED_KEYS = {"label", "start_date", "end_date", "meeting"}
SCHEDULE_COLUMNS = (
    "week",
    "date",
    "topic",
    "lecture",
    "presentation",
    "assignment",
    "notes",
)
ASSIGNMENT_REQUIRED_KEYS = {"title", "subjects", "notebook", "status"}
TOOL_REQUIRED_KEYS = {"title", "entrypoint", "runtime", "gallery"}

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ContentValidationError(ValueError):
    """Raised when metadata fails validation."""

    def __init__(self, source: Path | str, field_name: str, value: Any, message: str) -> None:
        self.source = Path(source)
        self.field_name = field_name
        self.value = value
        self.message = message
        super().__init__(f"{self.source}: {field_name}: {message} (got {value!r})")


def _fail(source: Path | str, field_name: str, value: Any, message: str) -> None:
    raise ContentValidationError(source, field_name, value, message)


def _warn_unknown_keys(source: Path, data: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(data) - allowed)
    for key in unknown:
        warnings.warn(
            f"{source}: unknown key {key!r} will be ignored",
            stacklevel=2,
        )


def _parse_iso_date(source: Path, field_name: str, raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str):
        _fail(source, field_name, raw, "expected an ISO date string YYYY-MM-DD")
    if not ISO_DATE.match(raw):
        _fail(source, field_name, raw, "expected an ISO date string YYYY-MM-DD")
    try:
        year, month, day = (int(part) for part in raw.split("-"))
        return date(year, month, day)
    except ValueError as exc:
        _fail(source, field_name, raw, f"invalid calendar date ({exc})")


def _lecture_number(slug: str) -> str:
    match = re.match(r"^([0-9]+[A-Za-z]?)", slug)
    return match.group(1) if match else slug


def _parse_bool(source: Path, field_name: str, raw: Any, *, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().casefold()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
        _fail(source, field_name, raw, "expected a boolean")
    _fail(source, field_name, raw, "expected a boolean")


def _week_sort_key(week: str) -> tuple[int, str]:
    if week.isdigit():
        return (0, f"{int(week):09d}")
    return (1, week.casefold())


def _lecture_sort_key(lecture: Lecture) -> tuple[int, str]:
    match = re.match(r"^(\d+)", lecture.number)
    return (int(match.group(1)), lecture.number) if match else (9999, lecture.number)


def _nonempty_string(source: Path, field_name: str, raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        _fail(source, field_name, raw, "expected a non-empty string")
    return raw.strip()


def _string_list(source: Path, field_name: str, raw: Any) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        _fail(source, field_name, raw, "expected a list of strings")
    return [item.strip() for item in raw if item.strip()]


@dataclass(frozen=True)
class CourseRepo:
    owner: str
    name: str
    branch: str


@dataclass(frozen=True)
class ColabConfig:
    enabled: bool


@dataclass(frozen=True)
class Instructor:
    name: str
    url: str = ""


@dataclass(frozen=True)
class Course:
    title: str
    repo: CourseRepo
    current_offering: str
    instructors: tuple[Instructor, ...]
    colab: ColabConfig
    source_path: Path


@dataclass(frozen=True)
class Meeting:
    time: str
    place: str


@dataclass(frozen=True)
class Offering:
    term: str
    label: str
    start_date: date | None
    end_date: date | None
    meeting: Meeting
    staff: tuple[dict[str, Any], ...]
    announcements: tuple[dict[str, Any], ...]
    grading_notes: str
    source_path: Path


@dataclass(frozen=True)
class ScheduleRow:
    week: str
    date: date | None
    topic: str
    lecture: str | None
    presentation: str | None
    assignment: str | None
    notes: str


@dataclass(frozen=True)
class OfferingSchedule:
    offering: Offering
    rows: tuple[ScheduleRow, ...]
    source_path: Path


@dataclass(frozen=True)
class LectureSurfaces:
    learn: str
    presentation: str


@dataclass(frozen=True)
class LectureApp:
    id: str
    title: str
    path: str
    runtime: str
    gallery: bool


@dataclass(frozen=True)
class Lecture:
    slug: str
    number: str
    title: str
    subjects: tuple[str, ...]
    status: str
    surfaces: LectureSurfaces
    apps: tuple[LectureApp, ...]
    source_path: Path


@dataclass(frozen=True)
class Assignment:
    slug: str
    title: str
    subjects: tuple[str, ...]
    estimated_time: str | None
    notebook: str
    related_lectures: tuple[str, ...]
    status: str
    source_path: Path


@dataclass(frozen=True)
class Tool:
    slug: str
    title: str
    summary: str
    entrypoint: str
    subjects: tuple[str, ...]
    runtime: str
    gallery: bool
    source_path: Path


@dataclass(frozen=True)
class ContentCatalog:
    course: Course
    offerings: tuple[OfferingSchedule, ...]
    lectures: tuple[Lecture, ...]
    assignments: tuple[Assignment, ...]
    tools: tuple[Tool, ...]


def load_yaml_mapping(source: Path) -> dict[str, Any]:
    if not source.exists():
        _fail(source, "<file>", source.name, "file does not exist")
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        _fail(source, "<root>", data, "expected a YAML mapping")
    return data


def load_course(source: Path | None = None) -> Course:
    source = source or CONTENT_DIR / "course.yml"
    data = load_yaml_mapping(source)
    _warn_unknown_keys(
        source,
        data,
        COURSE_REQUIRED_KEYS | {"instructors"},
    )

    for key in sorted(COURSE_REQUIRED_KEYS):
        if key not in data:
            _fail(source, key, None, "missing required field")

    title = _nonempty_string(source, "title", data["title"])

    repo_raw = data["repo"]
    if not isinstance(repo_raw, dict):
        _fail(source, "repo", repo_raw, "expected a mapping")
    repo = CourseRepo(
        owner=_nonempty_string(source, "repo.owner", repo_raw.get("owner")),
        name=_nonempty_string(source, "repo.name", repo_raw.get("name")),
        branch=_nonempty_string(source, "repo.branch", repo_raw.get("branch")),
    )

    current_offering = _nonempty_string(source, "current_offering", data["current_offering"])
    offering_dir = OFFERINGS_DIR / current_offering
    if not offering_dir.is_dir():
        _fail(
            source,
            "current_offering",
            current_offering,
            f"no offering directory at {offering_dir.relative_to(SITE_ROOT).as_posix()}",
        )

    colab_raw = data["colab"]
    if not isinstance(colab_raw, dict):
        _fail(source, "colab", colab_raw, "expected a mapping")
    colab_enabled = _parse_bool(source, "colab.enabled", colab_raw.get("enabled"), default=False)
    if colab_enabled:
        for repo_field in ("owner", "name", "branch"):
            if not getattr(repo, repo_field):
                _fail(source, f"repo.{repo_field}", "", "required when colab.enabled is true")

    instructors: list[Instructor] = []
    for index, entry in enumerate(data.get("instructors") or []):
        if not isinstance(entry, dict):
            _fail(source, f"instructors[{index}]", entry, "expected a mapping")
        name = _nonempty_string(source, f"instructors[{index}].name", entry.get("name"))
        url = entry.get("url") or ""
        if url is not None and not isinstance(url, str):
            _fail(source, f"instructors[{index}].url", url, "expected a string")
        instructors.append(Instructor(name=name, url=url.strip()))

    return Course(
        title=title,
        repo=repo,
        current_offering=current_offering,
        instructors=tuple(instructors),
        colab=ColabConfig(enabled=colab_enabled),
        source_path=source,
    )


def load_offering(term: str) -> Offering:
    offering_dir = OFFERINGS_DIR / term
    source = offering_dir / "offering.yml"
    data = load_yaml_mapping(source)
    _warn_unknown_keys(
        source,
        data,
        OFFERING_REQUIRED_KEYS | {"staff", "announcements", "grading_notes"},
    )

    for key in sorted(OFFERING_REQUIRED_KEYS):
        if key not in data:
            _fail(source, key, None, "missing required field")

    meeting_raw = data["meeting"]
    if not isinstance(meeting_raw, dict):
        _fail(source, "meeting", meeting_raw, "expected a mapping")

    return Offering(
        term=term,
        label=_nonempty_string(source, "label", data["label"]),
        start_date=_parse_iso_date(source, "start_date", data["start_date"]),
        end_date=_parse_iso_date(source, "end_date", data["end_date"]),
        meeting=Meeting(
            time=str(meeting_raw.get("time") or "").strip(),
            place=str(meeting_raw.get("place") or "").strip(),
        ),
        staff=tuple(data.get("staff") or []),
        announcements=tuple(data.get("announcements") or []),
        grading_notes=str(data.get("grading_notes") or "").strip(),
        source_path=source,
    )


def _optional_slug(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None


def load_schedule_csv(
    term: str,
    *,
    lecture_slugs: set[str],
    assignment_slugs: set[str],
) -> OfferingSchedule:
    offering = load_offering(term)
    source = OFFERINGS_DIR / term / "schedule.csv"
    if not source.exists():
        _fail(source, "<file>", source.name, "file does not exist")

    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(SCHEDULE_COLUMNS):
            _fail(
                source,
                "<header>",
                reader.fieldnames,
                f"expected columns {', '.join(SCHEDULE_COLUMNS)}",
            )

        rows: list[ScheduleRow] = []
        seen_weeks: set[str] = set()
        for line_number, raw_row in enumerate(reader, start=2):
            week = (raw_row.get("week") or "").strip()
            if not week:
                _fail(source, f"row {line_number}.week", week, "week identifier is required")
            if week in seen_weeks:
                _fail(source, f"row {line_number}.week", week, "duplicate week identifier")
            seen_weeks.add(week)

            parsed_date = _parse_iso_date(source, f"row {line_number}.date", raw_row.get("date"))
            lecture = _optional_slug(raw_row.get("lecture"))
            presentation = _optional_slug(raw_row.get("presentation"))
            assignment = _optional_slug(raw_row.get("assignment"))

            if lecture and lecture not in lecture_slugs:
                _fail(
                    source,
                    f"row {line_number}.lecture",
                    lecture,
                    "unknown lecture slug",
                )
            if presentation and presentation not in lecture_slugs:
                _fail(
                    source,
                    f"row {line_number}.presentation",
                    presentation,
                    "unknown lecture slug",
                )
            if assignment and assignment not in assignment_slugs:
                _fail(
                    source,
                    f"row {line_number}.assignment",
                    assignment,
                    "unknown assignment slug",
                )

            rows.append(
                ScheduleRow(
                    week=week,
                    date=parsed_date,
                    topic=(raw_row.get("topic") or "").strip(),
                    lecture=lecture,
                    presentation=presentation,
                    assignment=assignment,
                    notes=(raw_row.get("notes") or "").strip(),
                )
            )

    rows.sort(key=lambda row: _week_sort_key(row.week))
    return OfferingSchedule(offering=offering, rows=tuple(rows), source_path=source)


def _resolve_lecture_surfaces(
    directory: Path,
    manifest: dict[str, Any],
    source: Path,
) -> LectureSurfaces:
    surfaces_raw = manifest.get("surfaces")
    if isinstance(surfaces_raw, dict):
        learn = surfaces_raw.get("learn")
        presentation = surfaces_raw.get("presentation")
        if not learn or not presentation:
            _fail(source, "surfaces", surfaces_raw, "learn and presentation paths are required")
        learn_path = directory / str(learn)
        presentation_path = directory / str(presentation)
        if not learn_path.exists():
            _fail(source, "surfaces.learn", learn, f"missing file at {learn_path.name}")
        if not presentation_path.exists():
            _fail(
                source,
                "surfaces.presentation",
                presentation,
                f"missing file at {presentation_path.name}",
            )
        return LectureSurfaces(learn=str(learn), presentation=str(presentation))

    # Transitional compatibility for legacy manifests during migration.
    learn = manifest.get("canonical_source")
    if isinstance(learn, str) and (
        learn.startswith("lectures/") or learn.startswith("content/lectures/")
    ):
        learn_name = Path(learn).name
        learn_path = directory / learn_name
        if learn_path.exists():
            presentation = "slides.qmd" if (directory / "slides.qmd").exists() else learn_name
            return LectureSurfaces(learn=learn_name, presentation=presentation)

    default_learn = directory / "learn.ipynb"
    default_presentation = directory / "slides.qmd"
    legacy_notebook = directory / "notebook.ipynb"
    if default_learn.exists() and default_presentation.exists():
        return LectureSurfaces(learn="learn.ipynb", presentation="slides.qmd")
    if legacy_notebook.exists() and default_presentation.exists():
        return LectureSurfaces(learn="notebook.ipynb", presentation="slides.qmd")
    if legacy_notebook.exists():
        return LectureSurfaces(learn="notebook.ipynb", presentation="notebook.ipynb")

    _fail(
        source,
        "surfaces",
        manifest.get("surfaces"),
        "could not resolve learn and presentation surfaces",
    )


def _load_lecture_apps(manifest: dict[str, Any], source: Path) -> tuple[LectureApp, ...]:
    apps: list[LectureApp] = []
    apps_raw = manifest.get("apps")
    if isinstance(apps_raw, list):
        for index, entry in enumerate(apps_raw):
            if not isinstance(entry, dict):
                _fail(source, f"apps[{index}]", entry, "expected a mapping")
            apps.append(
                LectureApp(
                    id=_nonempty_string(source, f"apps[{index}].id", entry.get("id")),
                    title=_nonempty_string(source, f"apps[{index}].title", entry.get("title")),
                    path=_nonempty_string(source, f"apps[{index}].path", entry.get("path")),
                    runtime=str(entry.get("runtime") or "wasm-marimo"),
                    gallery=_parse_bool(
                        source,
                        f"apps[{index}].gallery",
                        entry.get("gallery"),
                        default=True,
                    ),
                )
            )
        return tuple(apps)

    runtime_apps = manifest.get("runtimes", {}).get("apps") if isinstance(manifest.get("runtimes"), dict) else None
    if isinstance(runtime_apps, list):
        for app_id in runtime_apps:
            if isinstance(app_id, str) and app_id.strip():
                apps.append(
                    LectureApp(
                        id=app_id.strip(),
                        title=app_id.strip(),
                        path=f"apps/{app_id.strip()}",
                        runtime="browser-native",
                        gallery=True,
                    )
                )
    return tuple(apps)


def discover_lectures(lectures_dir: Path | None = None) -> tuple[Lecture, ...]:
    lectures_dir = lectures_dir or LECTURES_DIR
    if not lectures_dir.is_dir():
        return ()

    lectures: list[Lecture] = []
    for directory in sorted(path for path in lectures_dir.iterdir() if path.is_dir()):
        manifest_path = directory / "manifest.yml"
        if not manifest_path.exists():
            continue

        manifest = load_yaml_mapping(manifest_path)
        title = manifest.get("title")
        if not isinstance(title, str) or not title.strip():
            _fail(manifest_path, "title", title, "expected a non-empty string")

        number_raw = manifest.get("number")
        number = str(number_raw).strip() if number_raw is not None else _lecture_number(directory.name)
        subjects = tuple(_string_list(manifest_path, "subjects", manifest.get("subjects")))
        status = str(manifest.get("status") or "planned").strip()
        surfaces = _resolve_lecture_surfaces(directory, manifest, manifest_path)

        lectures.append(
            Lecture(
                slug=directory.name,
                number=number,
                title=title.strip(),
                subjects=subjects,
                status=status,
                surfaces=surfaces,
                apps=_load_lecture_apps(manifest, manifest_path),
                source_path=manifest_path,
            )
        )

    lectures.sort(key=_lecture_sort_key)
    return tuple(lectures)


def discover_assignments(
    assignments_dir: Path | None = None,
    *,
    lectures_dir: Path | None = None,
) -> tuple[Assignment, ...]:
    assignments_dir = assignments_dir or ASSIGNMENTS_DIR
    if not assignments_dir.is_dir():
        return ()

    assignments: list[Assignment] = []
    lecture_slugs = {lecture.slug for lecture in discover_lectures(lectures_dir)}

    for directory in sorted(path for path in assignments_dir.iterdir() if path.is_dir()):
        manifest_path = directory / "manifest.yml"
        if not manifest_path.exists():
            continue

        manifest = load_yaml_mapping(manifest_path)
        for key in sorted(ASSIGNMENT_REQUIRED_KEYS):
            if key not in manifest:
                _fail(manifest_path, key, None, "missing required field")

        notebook = _nonempty_string(manifest_path, "notebook", manifest["notebook"])
        if Path(notebook).name == "solution.ipynb":
            _fail(
                manifest_path,
                "notebook",
                notebook,
                "solution.ipynb must not be declared as the published notebook",
            )
        notebook_path = directory / notebook
        if not notebook_path.exists():
            _fail(manifest_path, "notebook", notebook, "notebook file does not exist")

        subjects = _string_list(manifest_path, "subjects", manifest["subjects"])
        if not subjects:
            _fail(manifest_path, "subjects", manifest["subjects"], "expected a non-empty list")

        related = _string_list(manifest_path, "related_lectures", manifest.get("related_lectures"))
        for slug in related:
            if slug not in lecture_slugs:
                _fail(manifest_path, "related_lectures", slug, "unknown lecture slug")

        estimated = manifest.get("estimated_time")
        estimated_time = None
        if estimated is not None:
            if not isinstance(estimated, str) or not estimated.strip():
                _fail(manifest_path, "estimated_time", estimated, "expected a non-empty string")
            estimated_time = estimated.strip()

        assignments.append(
            Assignment(
                slug=directory.name,
                title=_nonempty_string(manifest_path, "title", manifest["title"]),
                subjects=tuple(subjects),
                estimated_time=estimated_time,
                notebook=notebook,
                related_lectures=tuple(related),
                status=_nonempty_string(manifest_path, "status", manifest["status"]),
                source_path=manifest_path,
            )
        )

    assignments.sort(key=lambda item: (item.subjects[0].casefold(), item.title.casefold()))
    return tuple(assignments)


def discover_tools(tools_dir: Path | None = None) -> tuple[Tool, ...]:
    tools_dir = tools_dir or TOOLS_DIR
    if not tools_dir.is_dir():
        return ()

    tools: list[Tool] = []
    for directory in sorted(path for path in tools_dir.iterdir() if path.is_dir()):
        manifest_path = directory / "manifest.yml"
        if not manifest_path.exists():
            continue

        manifest = load_yaml_mapping(manifest_path)
        for key in sorted(TOOL_REQUIRED_KEYS):
            if key not in manifest:
                _fail(manifest_path, key, None, "missing required field")

        entrypoint = _nonempty_string(manifest_path, "entrypoint", manifest["entrypoint"])
        entrypoint_path = directory / entrypoint
        if not entrypoint_path.exists():
            _fail(manifest_path, "entrypoint", entrypoint, "entrypoint file does not exist")

        tools.append(
            Tool(
                slug=directory.name,
                title=_nonempty_string(manifest_path, "title", manifest["title"]),
                summary=str(manifest.get("summary") or "").strip(),
                entrypoint=entrypoint,
                subjects=tuple(_string_list(manifest_path, "subjects", manifest.get("subjects"))),
                runtime=_nonempty_string(manifest_path, "runtime", manifest["runtime"]),
                gallery=_parse_bool(manifest_path, "gallery", manifest["gallery"]),
                source_path=manifest_path,
            )
        )

    tools.sort(key=lambda item: item.title.casefold())
    return tuple(tools)


def load_offerings(
    *,
    lecture_slugs: set[str] | None = None,
    assignment_slugs: set[str] | None = None,
) -> tuple[OfferingSchedule, ...]:
    if not OFFERINGS_DIR.is_dir():
        return ()

    if lecture_slugs is None:
        lecture_slugs = {lecture.slug for lecture in discover_lectures()}
    if assignment_slugs is None:
        assignment_slugs = {assignment.slug for assignment in discover_assignments()}

    offerings: list[OfferingSchedule] = []
    for offering_dir in sorted(path for path in OFFERINGS_DIR.iterdir() if path.is_dir()):
        offerings.append(
            load_schedule_csv(
                offering_dir.name,
                lecture_slugs=lecture_slugs,
                assignment_slugs=assignment_slugs,
            )
        )

    offerings.sort(key=lambda item: item.offering.term)
    return tuple(offerings)


def load_catalog(
    *,
    lectures_dir: Path | None = None,
    assignments_dir: Path | None = None,
    tools_dir: Path | None = None,
) -> ContentCatalog:
    lectures = discover_lectures(lectures_dir)
    assignments = discover_assignments(assignments_dir, lectures_dir=lectures_dir)
    lecture_slugs = {lecture.slug for lecture in lectures}
    assignment_slugs = {assignment.slug for assignment in assignments}
    offerings = load_offerings(
        lecture_slugs=lecture_slugs,
        assignment_slugs=assignment_slugs,
    )
    course = load_course()
    current_terms = {offering.offering.term for offering in offerings}
    if course.current_offering not in current_terms:
        _fail(
            course.source_path,
            "current_offering",
            course.current_offering,
            "offering has no schedule.csv",
        )

    return ContentCatalog(
        course=course,
        offerings=offerings,
        lectures=lectures,
        assignments=assignments,
        tools=discover_tools(tools_dir),
    )


def current_offering_schedule(catalog: ContentCatalog) -> OfferingSchedule:
    for offering in catalog.offerings:
        if offering.offering.term == catalog.course.current_offering:
            return offering
    _fail(
        catalog.course.source_path,
        "current_offering",
        catalog.course.current_offering,
        "current offering schedule not found",
    )


def main() -> None:
    catalog = load_catalog()
    print(
        f"Validated catalog: {len(catalog.lectures)} lecture(s), "
        f"{len(catalog.assignments)} assignment(s), "
        f"{len(catalog.offerings)} offering(s)."
    )


if __name__ == "__main__":
    main()
