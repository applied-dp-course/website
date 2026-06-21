"""Build Open in Colab URLs from course repository configuration."""

from __future__ import annotations

from urllib.parse import quote

COLAB_BASE_URL = "https://colab.research.google.com/github"
COLAB_BADGE_URL = "https://colab.research.google.com/assets/colab-badge.svg"
DEFAULT_BADGE_LABEL = "Open in Colab"


def notebook_url(
    *,
    owner: str,
    name: str,
    branch: str,
    repo_relative_path: str,
) -> str:
    """Return a Colab notebook URL for a repository-relative source path."""
    normalized = repo_relative_path.replace("\\", "/").lstrip("/")
    encoded_path = quote(normalized, safe="/")
    return f"{COLAB_BASE_URL}/{owner}/{name}/blob/{branch}/{encoded_path}"


def badge_markdown(url: str, *, label: str = DEFAULT_BADGE_LABEL) -> str:
    """Return a Markdown image link for the standard Colab badge."""
    return f"[![{label}]({COLAB_BADGE_URL})]({url})"


def badge_for_notebook(
    *,
    enabled: bool,
    owner: str,
    name: str,
    branch: str,
    repo_relative_path: str,
    label: str = DEFAULT_BADGE_LABEL,
) -> str:
    """Return a Colab badge when enabled, otherwise an empty string."""
    if not enabled:
        return ""
    url = notebook_url(
        owner=owner,
        name=name,
        branch=branch,
        repo_relative_path=repo_relative_path,
    )
    return badge_markdown(url, label=label)
