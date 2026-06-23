"""Load and validate the course's authored content and offering schedules."""

from __future__ import annotations

import csv
import json
import re
import warnings
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


SITE_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = SITE_ROOT / "_generated"
PAGES_DIR = SITE_ROOT / "pages"
CONTENT_DIR = SITE_ROOT / "content"
LECTURE_PRESENTATIONS_DIR = CONTENT_DIR / "lecture-presentations"
BLOG_POSTS_DIR = CONTENT_DIR / "blog-posts"
CLASS_ASSIGNMENTS_DIR = CONTENT_DIR / "class-assignments"
HOME_ASSIGNMENTS_DIR = CONTENT_DIR / "home-assignments"
OFFERINGS_DIR = CONTENT_DIR / "offerings"
TOOLS_DIR = CONTENT_DIR / "tools"
SITE_POSTS_DIR = CONTENT_DIR / "site-posts"

LECTURE_PRESENTATIONS_URL_PREFIX = "content/lecture-presentations"
BLOG_POSTS_URL_PREFIX = "content/blog-posts"
CLASS_ASSIGNMENTS_URL_PREFIX = "content/class-assignments"
HOME_ASSIGNMENTS_URL_PREFIX = "content/home-assignments"

# Compatibility names retained for helper modules while the public model uses the
# explicit content-type names above.
LECTURES_DIR = LECTURE_PRESENTATIONS_DIR
ASSIGNMENTS_DIR = CLASS_ASSIGNMENTS_DIR
LECTURES_URL_PREFIX = LECTURE_PRESENTATIONS_URL_PREFIX
ASSIGNMENTS_URL_PREFIX = CLASS_ASSIGNMENTS_URL_PREFIX

COURSE_REQUIRED_KEYS = {"title", "repo", "current_offering", "colab"}
OFFERING_REQUIRED_KEYS = {"label", "start_date", "end_date", "meeting"}
SCHEDULE_COLUMNS = (
    "week",
    "date",
    "topic",
    "blog_post",
    "lecture_presentation",
    "class_assignment",
    "home_assignment",
    "notes",
)
ITEM_REQUIRED_KEYS = {"title", "entrypoint", "status"}
TOOL_REQUIRED_KEYS = {"title", "entrypoint", "runtime", "gallery"}
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STABLE_NAME = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
NUMBERED_NAME = re.compile(r"^\d+[-_]")
GENERATED_FILE_SUFFIXES = (".html", ".quarto_ipynb")
GENERATED_DIRECTORY_NAMES = {"apps", ".jupyter_cache"}


class ContentValidationError(ValueError):
    def __init__(self, source: Path | str, field_name: str, value: Any, message: str) -> None:
        self.source = Path(source)
        self.field_name = field_name
        self.value = value
        self.message = message
        super().__init__(f"{self.source}: {field_name}: {message} (got {value!r})")


def _fail(source: Path | str, field_name: str, value: Any, message: str) -> None:
    raise ContentValidationError(source, field_name, value, message)


def _warn_unknown_keys(source: Path, data: dict[str, Any], allowed: set[str]) -> None:
    for key in sorted(set(data) - allowed):
        warnings.warn(f"{source}: unknown key {key!r} will be ignored", stacklevel=2)


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


def _parse_iso_date(source: Path, field_name: str, raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    if not isinstance(raw, str) or not ISO_DATE.match(raw):
        _fail(source, field_name, raw, "expected an ISO date string YYYY-MM-DD")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        _fail(source, field_name, raw, f"invalid calendar date ({exc})")


def _week_sort_key(week: str) -> tuple[int, str]:
    return (0, f"{int(week):09d}") if week.isdigit() else (1, week.casefold())


def _validate_name(source: Path, name: str) -> None:
    if NUMBERED_NAME.match(name):
        _fail(source, "name", name, "content names must not start with a number")
    if not STABLE_NAME.match(name):
        _fail(source, "name", name, "expected a lowercase kebab-case name")


def validate_content_source_tree() -> None:
    """Reject generated artifacts and numbered internal paths under authored collections."""

    collections = (
        LECTURE_PRESENTATIONS_DIR,
        BLOG_POSTS_DIR,
        CLASS_ASSIGNMENTS_DIR,
        HOME_ASSIGNMENTS_DIR,
    )
    for collection in collections:
        if not collection.is_dir():
            continue
        for path in collection.rglob("*"):
            relative = path.relative_to(collection)
            for part in relative.parts:
                if NUMBERED_NAME.match(part):
                    _fail(path, "path", relative.as_posix(), "internal content paths must not be numbered")
            if path.is_dir() and (
                path.name in GENERATED_DIRECTORY_NAMES or path.name.endswith("_files")
            ):
                _fail(path, "path", relative.as_posix(), "generated directories are not allowed under content")
            if path.is_file() and (
                path.name == ".libdpy-interactive"
                or path.name.endswith(GENERATED_FILE_SUFFIXES)
            ):
                _fail(path, "path", relative.as_posix(), "generated files are not allowed under content")
            if path.is_file() and path.suffix == ".ipynb":
                notebook = json.loads(path.read_text(encoding="utf-8"))
                if any(cell.get("outputs") for cell in notebook.get("cells", [])):
                    _fail(path, "outputs", path.name, "notebook outputs must be cleared before commit")
                kernelspec = notebook.get("metadata", {}).get("kernelspec", {})
                if not isinstance(kernelspec, dict):
                    _fail(path, "kernelspec", kernelspec, "expected a mapping")
                kernel_name = kernelspec.get("name")
                if kernel_name != "python3":
                    _fail(
                        path,
                        "kernelspec.name",
                        kernel_name,
                        "content notebooks must use the python3 kernel for CI rendering",
                    )
                if "path" in kernelspec:
                    _fail(
                        path,
                        "kernelspec.path",
                        kernelspec["path"],
                        "local kernel paths must not be committed in content notebooks",
                    )
                if "widgets" in notebook.get("metadata", {}):
                    _fail(
                        path,
                        "metadata.widgets",
                        "present",
                        "notebook widget state must be cleared before commit",
                    )


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
    blog_post: str | None
    lecture_presentation: str | None
    class_assignment: str | None
    home_assignment: str | None
    notes: str


@dataclass(frozen=True)
class OfferingSchedule:
    offering: Offering
    rows: tuple[ScheduleRow, ...]
    source_path: Path


@dataclass(frozen=True)
class ContentApp:
    id: str
    title: str
    path: str
    runtime: str
    gallery: bool


@dataclass(frozen=True)
class ContentItem:
    name: str
    title: str
    kind: str
    entrypoint: str
    subjects: tuple[str, ...]
    status: str
    estimated_time: str | None
    related: tuple[str, ...]
    apps: tuple[ContentApp, ...]
    source_path: Path

    @property
    def slug(self) -> str:
        return self.name

    @property
    def number(self) -> str:
        return self.name

    @property
    def public_path(self) -> str:
        return self.source_path.parent.joinpath(self.entrypoint).relative_to(SITE_ROOT).as_posix()


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
    lecture_presentations: tuple[ContentItem, ...]
    blog_posts: tuple[ContentItem, ...]
    class_assignments: tuple[ContentItem, ...]
    home_assignments: tuple[ContentItem, ...]
    tools: tuple[Tool, ...]

    @property
    def lectures(self) -> tuple[ContentItem, ...]:
        return self.lecture_presentations

    @property
    def assignments(self) -> tuple[ContentItem, ...]:
        return self.class_assignments + self.home_assignments


# Compatibility aliases for imports in helper modules.
LectureApp = ContentApp
Lecture = ContentItem
Assignment = ContentItem


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
    _warn_unknown_keys(source, data, COURSE_REQUIRED_KEYS | {"instructors"})
    for key in sorted(COURSE_REQUIRED_KEYS):
        if key not in data:
            _fail(source, key, None, "missing required field")

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
        _fail(source, "current_offering", current_offering, "offering directory does not exist")

    colab_raw = data["colab"]
    if not isinstance(colab_raw, dict):
        _fail(source, "colab", colab_raw, "expected a mapping")

    instructors: list[Instructor] = []
    for index, entry in enumerate(data.get("instructors") or []):
        if not isinstance(entry, dict):
            _fail(source, f"instructors[{index}]", entry, "expected a mapping")
        instructors.append(
            Instructor(
                name=_nonempty_string(source, f"instructors[{index}].name", entry.get("name")),
                url=str(entry.get("url") or "").strip(),
            )
        )
    return Course(
        title=_nonempty_string(source, "title", data["title"]),
        repo=repo,
        current_offering=current_offering,
        instructors=tuple(instructors),
        colab=ColabConfig(_parse_bool(source, "colab.enabled", colab_raw.get("enabled"))),
        source_path=source,
    )


def load_offering(term: str) -> Offering:
    source = OFFERINGS_DIR / term / "offering.yml"
    data = load_yaml_mapping(source)
    _warn_unknown_keys(
        source,
        data,
        OFFERING_REQUIRED_KEYS | {"staff", "announcements", "grading_notes"},
    )
    for key in sorted(OFFERING_REQUIRED_KEYS):
        if key not in data:
            _fail(source, key, None, "missing required field")
    meeting = data["meeting"]
    if not isinstance(meeting, dict):
        _fail(source, "meeting", meeting, "expected a mapping")
    return Offering(
        term=term,
        label=_nonempty_string(source, "label", data["label"]),
        start_date=_parse_iso_date(source, "start_date", data["start_date"]),
        end_date=_parse_iso_date(source, "end_date", data["end_date"]),
        meeting=Meeting(str(meeting.get("time") or "").strip(), str(meeting.get("place") or "").strip()),
        staff=tuple(data.get("staff") or []),
        announcements=tuple(data.get("announcements") or []),
        grading_notes=str(data.get("grading_notes") or "").strip(),
        source_path=source,
    )


def _load_apps(source: Path, raw: Any) -> tuple[ContentApp, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        _fail(source, "apps", raw, "expected a list")
    apps: list[ContentApp] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            _fail(source, f"apps[{index}]", entry, "expected a mapping")
        apps.append(
            ContentApp(
                id=_nonempty_string(source, f"apps[{index}].id", entry.get("id")),
                title=_nonempty_string(source, f"apps[{index}].title", entry.get("title")),
                path=_nonempty_string(source, f"apps[{index}].path", entry.get("path")),
                runtime=str(entry.get("runtime") or "browser-native").strip(),
                gallery=_parse_bool(source, f"apps[{index}].gallery", entry.get("gallery"), default=True),
            )
        )
    return tuple(apps)


def discover_items(directory: Path, kind: str, expected_suffix: str) -> tuple[ContentItem, ...]:
    if not directory.is_dir():
        return ()
    items: list[ContentItem] = []
    for item_dir in sorted(path for path in directory.iterdir() if path.is_dir()):
        source = item_dir / "manifest.yml"
        if not source.exists():
            _fail(item_dir, "manifest.yml", None, "each content item requires a hand-written manifest")
        _validate_name(source, item_dir.name)
        data = load_yaml_mapping(source)
        _warn_unknown_keys(
            source,
            data,
            ITEM_REQUIRED_KEYS | {"subjects", "estimated_time", "related", "apps"},
        )
        for key in sorted(ITEM_REQUIRED_KEYS):
            if key not in data:
                _fail(source, key, None, "missing required field")
        entrypoint = _nonempty_string(source, "entrypoint", data["entrypoint"])
        entrypoint_path = item_dir / entrypoint
        if (
            kind in {"class-assignment", "home-assignment"}
            and entrypoint_path.name == "solution.ipynb"
        ):
            _fail(
                source,
                "entrypoint",
                entrypoint,
                "solution.ipynb cannot be a published entrypoint",
            )
        if entrypoint_path.suffix != expected_suffix:
            _fail(source, "entrypoint", entrypoint, f"expected a {expected_suffix} file")
        if not entrypoint_path.is_file():
            _fail(source, "entrypoint", entrypoint, "entrypoint file does not exist")
        estimated = data.get("estimated_time")
        if estimated is not None:
            estimated = _nonempty_string(source, "estimated_time", estimated)
        items.append(
            ContentItem(
                name=item_dir.name,
                title=_nonempty_string(source, "title", data["title"]),
                kind=kind,
                entrypoint=entrypoint,
                subjects=tuple(_string_list(source, "subjects", data.get("subjects"))),
                status=_nonempty_string(source, "status", data["status"]),
                estimated_time=estimated,
                related=tuple(_string_list(source, "related", data.get("related"))),
                apps=_load_apps(source, data.get("apps")),
                source_path=source,
            )
        )
    return tuple(sorted(items, key=lambda item: (item.title.casefold(), item.name)))


def discover_lecture_presentations(directory: Path | None = None) -> tuple[ContentItem, ...]:
    return discover_items(directory or LECTURE_PRESENTATIONS_DIR, "lecture-presentation", ".qmd")


def discover_blog_posts(directory: Path | None = None) -> tuple[ContentItem, ...]:
    return discover_items(directory or BLOG_POSTS_DIR, "blog-post", ".ipynb")


def discover_class_assignments(directory: Path | None = None) -> tuple[ContentItem, ...]:
    return discover_items(directory or CLASS_ASSIGNMENTS_DIR, "class-assignment", ".ipynb")


def discover_home_assignments(directory: Path | None = None) -> tuple[ContentItem, ...]:
    return discover_items(directory or HOME_ASSIGNMENTS_DIR, "home-assignment", ".ipynb")


def discover_lectures(lectures_dir: Path | None = None) -> tuple[ContentItem, ...]:
    return discover_lecture_presentations(lectures_dir)


def discover_assignments(
    assignments_dir: Path | None = None,
    *,
    lectures_dir: Path | None = None,
) -> tuple[ContentItem, ...]:
    del lectures_dir
    return discover_class_assignments(assignments_dir)


def discover_tools(tools_dir: Path | None = None) -> tuple[Tool, ...]:
    tools_dir = tools_dir or TOOLS_DIR
    if not tools_dir.is_dir():
        return ()
    tools: list[Tool] = []
    for directory in sorted(path for path in tools_dir.iterdir() if path.is_dir()):
        source = directory / "manifest.yml"
        if not source.exists():
            continue
        data = load_yaml_mapping(source)
        for key in sorted(TOOL_REQUIRED_KEYS):
            if key not in data:
                _fail(source, key, None, "missing required field")
        entrypoint = _nonempty_string(source, "entrypoint", data["entrypoint"])
        if not (directory / entrypoint).is_file():
            _fail(source, "entrypoint", entrypoint, "entrypoint file does not exist")
        tools.append(
            Tool(
                slug=directory.name,
                title=_nonempty_string(source, "title", data["title"]),
                summary=str(data.get("summary") or "").strip(),
                entrypoint=entrypoint,
                subjects=tuple(_string_list(source, "subjects", data.get("subjects"))),
                runtime=_nonempty_string(source, "runtime", data["runtime"]),
                gallery=_parse_bool(source, "gallery", data["gallery"]),
                source_path=source,
            )
        )
    return tuple(sorted(tools, key=lambda item: item.title.casefold()))


def _optional_name(raw: Any) -> str | None:
    value = str(raw or "").strip()
    return value or None


def load_schedule_csv(term: str, *, known_names: dict[str, set[str]]) -> OfferingSchedule:
    offering = load_offering(term)
    source = OFFERINGS_DIR / term / "schedule.csv"
    if not source.exists():
        _fail(source, "<file>", source.name, "file does not exist")
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(SCHEDULE_COLUMNS):
            _fail(source, "<header>", reader.fieldnames, f"expected columns {', '.join(SCHEDULE_COLUMNS)}")
        rows: list[ScheduleRow] = []
        seen_weeks: set[str] = set()
        for line_number, raw in enumerate(reader, start=2):
            week = str(raw.get("week") or "").strip()
            if not week:
                _fail(source, f"row {line_number}.week", week, "week identifier is required")
            if week in seen_weeks:
                _fail(source, f"row {line_number}.week", week, "duplicate week identifier")
            seen_weeks.add(week)
            references = {
                field: _optional_name(raw.get(field))
                for field in (
                    "blog_post",
                    "lecture_presentation",
                    "class_assignment",
                    "home_assignment",
                )
            }
            for field, value in references.items():
                if value and value not in known_names[field]:
                    _fail(source, f"row {line_number}.{field}", value, f"unknown {field} name")
            rows.append(
                ScheduleRow(
                    week=week,
                    date=_parse_iso_date(source, f"row {line_number}.date", raw.get("date")),
                    topic=str(raw.get("topic") or "").strip(),
                    blog_post=references["blog_post"],
                    lecture_presentation=references["lecture_presentation"],
                    class_assignment=references["class_assignment"],
                    home_assignment=references["home_assignment"],
                    notes=str(raw.get("notes") or "").strip(),
                )
            )
    rows.sort(key=lambda row: _week_sort_key(row.week))
    return OfferingSchedule(offering, tuple(rows), source)


def load_offerings(*, known_names: dict[str, set[str]]) -> tuple[OfferingSchedule, ...]:
    if not OFFERINGS_DIR.is_dir():
        return ()
    offerings = [
        load_schedule_csv(directory.name, known_names=known_names)
        for directory in sorted(path for path in OFFERINGS_DIR.iterdir() if path.is_dir())
    ]
    return tuple(sorted(offerings, key=lambda item: item.offering.term))


def load_catalog(
    *,
    lecture_presentations_dir: Path | None = None,
    blog_posts_dir: Path | None = None,
    class_assignments_dir: Path | None = None,
    home_assignments_dir: Path | None = None,
    tools_dir: Path | None = None,
    lectures_dir: Path | None = None,
    assignments_dir: Path | None = None,
) -> ContentCatalog:
    validate_content_source_tree()
    presentations = discover_lecture_presentations(lecture_presentations_dir or lectures_dir)
    blog_posts = discover_blog_posts(blog_posts_dir)
    class_assignments = discover_class_assignments(class_assignments_dir or assignments_dir)
    home_assignments = discover_home_assignments(home_assignments_dir)
    known_names = {
        "blog_post": {item.name for item in blog_posts},
        "lecture_presentation": {item.name for item in presentations},
        "class_assignment": {item.name for item in class_assignments},
        "home_assignment": {item.name for item in home_assignments},
    }
    offerings = load_offerings(known_names=known_names)
    course = load_course()
    if course.current_offering not in {item.offering.term for item in offerings}:
        _fail(course.source_path, "current_offering", course.current_offering, "offering has no schedule.csv")
    return ContentCatalog(
        course=course,
        offerings=offerings,
        lecture_presentations=presentations,
        blog_posts=blog_posts,
        class_assignments=class_assignments,
        home_assignments=home_assignments,
        tools=discover_tools(tools_dir),
    )


def current_offering_schedule(catalog: ContentCatalog) -> OfferingSchedule:
    for offering in catalog.offerings:
        if offering.offering.term == catalog.course.current_offering:
            return offering
    _fail(catalog.course.source_path, "current_offering", catalog.course.current_offering, "schedule not found")


def main() -> None:
    catalog = load_catalog()
    print(
        "Validated catalog: "
        f"{len(catalog.lecture_presentations)} presentation(s), "
        f"{len(catalog.blog_posts)} blog post(s), "
        f"{len(catalog.class_assignments)} class assignment(s), "
        f"{len(catalog.home_assignments)} home assignment(s), "
        f"{len(catalog.offerings)} offering(s)."
    )


if __name__ == "__main__":
    main()
