#!/usr/bin/env bash
#
# Fail-closed "ship this lecture" gate. Runs the AUTHORING.md delivery gate mechanically
# so it cannot be skipped under pressure, and — only with --push — pushes and blocks on a
# GREEN GitHub Actions build+deploy. "Local render passed" and "pub_lib tag pushed" are NOT
# shipping; a lecture is shipped only when CI deploys the content commit to Pages.
#
# The failure this guards against: website deck/post imports libdpy symbols that were renamed
# or removed, the pin/tag ordering is wrong, or CI fails on render while local looked fine.
#
# Usage:
#   dev/tools/deliver_lecture.sh --slug <slug> [--slug <slug> ...] \
#       [--push] [--allow-dirty] [--base-url URL] [--expect STRING]
#
# Steps:
#   1. Preconditions   — repo/venv sane; each slug is real (content + baseline-routes + content-model)
#   2. Library / pin   — pinned pub_lib tag exists; sync it; verify content imports resolve on it
#   3. Validate        — pytest; full render; site route/link check; scoped smoke
#   4. Publish (--push)— clean tree required; push; watch CI to green; optional live-URL check
#
# Exit non-zero on the first failing gate. Nothing is pushed unless --push is given AND steps 1-3 pass.

set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }
ok()   { echo "  OK: $*"; }

# --- args --------------------------------------------------------------------
SLUGS=()
DO_PUSH=0
ALLOW_DIRTY=0
BASE_URL=""
EXPECT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug)       SLUGS+=("${2:-}"); shift 2 ;;
    --push)       DO_PUSH=1; shift ;;
    --allow-dirty) ALLOW_DIRTY=1; shift ;;
    --base-url)   BASE_URL="${2:-}"; shift 2 ;;
    --expect)     EXPECT="${2:-}"; shift 2 ;;
    -h|--help)    sed -n '2,32p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ ${#SLUGS[@]} -gt 0 ]] || die "at least one --slug is required"

# --- 1. preconditions --------------------------------------------------------
step "1. Preconditions"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || die "not inside a git repository"
cd "$ROOT"
[[ -f _quarto.yml && -d dev/tools ]] || die "run inside the website repo (no _quarto.yml/dev/tools here)"
PY="$ROOT/.venv/bin/python"
[[ -x "$PY" ]] || die "website venv missing: $PY (create it and pip install -r requirements-ci.txt)"

for slug in "${SLUGS[@]}"; do
  [[ -n "$slug" ]] || die "empty --slug"
  compgen -G "content/*/${slug}" >/dev/null || die "slug '${slug}' has no directory under content/*/"
  grep -q "/${slug}/" dev/plan/baseline-routes.json \
    || die "slug '${slug}' is not in dev/plan/baseline-routes.json (add its .html route in the same commit)"
  grep -q "${slug}" tests/test_content_model.py \
    || die "slug '${slug}' is not referenced in tests/test_content_model.py (update the named-collection sets)"
  ok "slug '${slug}' is registered (content + baseline-routes + content-model)"
done

DIRTY=0
[[ -n "$(git status --porcelain)" ]] && DIRTY=1
if [[ "$DO_PUSH" -eq 1 && "$DIRTY" -eq 1 ]]; then
  die "--push requires a clean tree so what is validated equals what is pushed — commit first"
fi
if [[ "$DIRTY" -eq 1 && "$ALLOW_DIRTY" -eq 0 ]]; then
  die "working tree is dirty; commit, or pass --allow-dirty to validate the working tree as-is"
fi

SLUG_ARGS=()
for slug in "${SLUGS[@]}"; do SLUG_ARGS+=(--slug "$slug"); done

# --- 2. library / pin --------------------------------------------------------
step "2. Library / pin"
PIN="$(grep -oE 'pub_lib\.git@\S+' requirements.txt | sed -E 's/.*@//')" \
  || die "could not read the libdpy pin from requirements.txt"
[[ -n "$PIN" ]] || die "requirements.txt libdpy line is unpinned (expected @vX.Y.Z)"
echo "  libdpy pin: ${PIN}"

if git ls-remote --exit-code --tags \
    https://github.com/applied-dp-course/pub_lib.git "refs/tags/${PIN}" >/dev/null 2>&1; then
  ok "pub_lib tag ${PIN} exists"
else
  die "pub_lib has no tag ${PIN} — release/tag libdpy before pinning content to it (do not push ahead of the tag)"
fi

./dev/tools/sync_libdpy.sh
"$PY" dev/tools/verify_libdpy_imports.py "${SLUG_ARGS[@]}" \
  || die "content imports symbols missing from libdpy ${PIN} (see list above) — align content + pin, or release the version that provides them"
ok "content libdpy imports resolve on ${PIN}"

# --- 3. validate -------------------------------------------------------------
step "3. Validate (pytest -> full render -> site check -> scoped smoke)"
"$PY" -m pytest tests -q
ok "unit tests pass"

# We just synced in step 2; skip render.sh's redundant re-sync.
LIBDPY_SYNC=0 ./dev/tools/render.sh
ok "full site render succeeded"

"$PY" scripts/check_site.py
ok "rendered routes and internal links verified"

"$PY" tests/run_smoke_tests.py "${SLUG_ARGS[@]}" --include-per-app
ok "scoped smoke passed (no-op is fine for static-figure slugs)"

if [[ "$DO_PUSH" -eq 0 ]]; then
  step "Gate passed. Not pushing (no --push)."
  echo "  Commit the content + pin, then re-run with --push (clean tree) to ship and confirm CI."
  exit 0
fi

# --- 4. publish --------------------------------------------------------------
step "4. Publish"
BRANCH="$(git branch --show-current)"
[[ "$BRANCH" == "main" ]] || echo "  NOTE: on '$BRANCH', not 'main' — Pages deploys only from main; a push here needs a PR whose build-check passes."

git push origin "HEAD:${BRANCH}"
SHA="$(git rev-parse HEAD)"
echo "  pushed ${SHA:0:7} to origin/${BRANCH}"

if ! command -v gh >/dev/null 2>&1; then
  echo
  echo "  WARNING: 'gh' not found — CI result NOT confirmed. This is NOT shipped yet."
  echo "  Watch: https://github.com/applied-dp-course/website/actions  (workflow: Publish website)"
  echo "  Ship only when the 'build' and 'deploy' jobs on ${SHA:0:7} are green."
  exit 0
fi

step "Waiting for the 'Publish website' build+deploy on ${SHA:0:7}"
RUN_ID=""
for attempt in $(seq 1 30); do
  RUN_ID="$(gh run list --workflow "Publish website" --commit "$SHA" --limit 1 \
    --json databaseId -q '.[0].databaseId' 2>/dev/null || true)"
  [[ -n "$RUN_ID" && "$RUN_ID" != "null" ]] && break
  echo "  waiting for the workflow run to register (attempt ${attempt}/30)..."
  sleep 4
done
[[ -n "$RUN_ID" && "$RUN_ID" != "null" ]] \
  || die "no 'Publish website' run found for ${SHA:0:7}; check the Actions tab (is the push event configured?)"

gh run watch "$RUN_ID" --exit-status \
  || die "CI failed for ${SHA:0:7} (run $RUN_ID) — the lecture is NOT shipped; open the run to see the failing job"
ok "CI build+deploy succeeded (run $RUN_ID)"

if [[ -n "$BASE_URL" && -n "$EXPECT" ]]; then
  step "Confirming the live site serves the new content"
  for attempt in $(seq 1 10); do
    if curl -fsSL "$BASE_URL" | grep -qF "$EXPECT"; then
      ok "live URL contains expected marker: '${EXPECT}'"
      break
    fi
    [[ "$attempt" -eq 10 ]] && die "live URL never showed '${EXPECT}' — Pages may still be propagating, or the old page is cached"
    echo "  not yet visible; retrying in 15s (${attempt}/10)..."
    sleep 15
  done
fi

step "Shipped: '${SLUGS[*]}' rendered, CI-green, and deployed."
