#!/usr/bin/env bash
#
# gen-notes.sh — categorize commits since the previous tag into Keep-a-Changelog
# sections and maintain CHANGELOG.md.
#
# Reads:  KYOTO_VERSION (required, no leading v), KYOTO_REPO_URL (optional).
# Writes: "notes" to $GITHUB_OUTPUT, and prepends a dated section to CHANGELOG.md.
#
# Commits are bucketed by the leading verb of the subject (the imperative style
# used across the Kyoto repos), with Security and Dependencies detected by content.
set -euo pipefail

VERSION="${KYOTO_VERSION:?KYOTO_VERSION is required}"
REPO_URL="${KYOTO_REPO_URL:-}"
CURRENT_TAG="v${VERSION}"
DATE="$(date +%Y-%m-%d)"

# --- Determine the previous tag reachable from HEAD (excluding the current one).
PREV_TAG="$(git tag --sort=-creatordate --merged HEAD 2>/dev/null \
  | grep -vxF "$CURRENT_TAG" | head -n1 || true)"

if [ -n "$PREV_TAG" ]; then
  RANGE="${PREV_TAG}..HEAD"
else
  RANGE="HEAD"   # first release: include all history
fi

# --- Collect commit subjects (hash <US> subject <US> author), newest first.
US=$'\x1f'
COMMITS=()
while IFS= read -r line; do
  [ -n "$line" ] && COMMITS+=("$line")
done < <(git log "$RANGE" --no-merges --pretty=format:"%h${US}%s${US}%an")

ADDED=(); FIXED=(); CHANGED=(); REMOVED=(); SECURITY=(); DEPS=(); OTHER=()

for c in "${COMMITS[@]}"; do
  hash="${c%%${US}*}"
  rest="${c#*${US}}"
  subject="${rest%%${US}*}"
  author="${rest#*${US}}"
  line="- ${subject} (\`${hash}\`)"
  lc="${subject,,}"          # bash lowercase, no subshell
  authlc="${author,,}"
  first="${lc%% *}"

  # Pure bash matching (no grep) — avoids SIGPIPE/SIGABRT and keeps word-ish
  # boundaries so e.g. "redesign" does not match the "sign" security keyword.
  if [[ "$lc" =~ (secur|vuln|cve|secret|harden|exploit) \
        || "$lc" =~ (^|[^a-z])sign(s|ed|ing|ature)?([^a-z]|$) ]]; then
    SECURITY+=("$line")
  elif [[ "$authlc" == *dependabot* \
          || "$first" =~ ^(bump|bumps|bumped|upgrade|upgrades|upgraded)$ ]]; then
    DEPS+=("$line")
  else
    case "$first" in
      add|adds|added|introduce*|implement*|create*|created|support*|enable*|enabled|expose*|exposed|persist*|track|tracks|tracked)
        ADDED+=("$line") ;;
      fix|fixes|fixed|resolve*|resolved|correct*|corrected|patch|patches|patched|repair*|repaired|prevent*|prevented)
        FIXED+=("$line") ;;
      remove*|removed|delete*|deleted|drop*|dropped|strip*|stripped|prune*|pruned|disable*|disabled)
        REMOVED+=("$line") ;;
      change*|changed|update*|updated|improve*|improved|enhance*|enhanced|refactor*|rework*|reworked|rename*|renamed|move*|moved|adjust*|adjusted|tune*|tuned|tweak*|tweaked|expand*|expanded|simplif*|revert*|reverted|round*|rounded|clarif*|migrate*|migrated)
        CHANGED+=("$line") ;;
      *)
        OTHER+=("$line") ;;
    esac
  fi
done

# --- Build the notes body.
NOTES_FILE="$(mktemp)"
emit() {  # emit "<title>" "${ARR[@]}"
  local title="$1"; shift
  if [ "$#" -gt 0 ]; then
    {
      printf '### %s\n' "$title"
      printf '%s\n' "$@"
      printf '\n'
    } >> "$NOTES_FILE"
  fi
}

emit "Added"        ${ADDED[@]+"${ADDED[@]}"}
emit "Fixed"        ${FIXED[@]+"${FIXED[@]}"}
emit "Changed"      ${CHANGED[@]+"${CHANGED[@]}"}
emit "Removed"      ${REMOVED[@]+"${REMOVED[@]}"}
emit "Security"     ${SECURITY[@]+"${SECURITY[@]}"}
emit "Dependencies" ${DEPS[@]+"${DEPS[@]}"}
emit "Other"        ${OTHER[@]+"${OTHER[@]}"}

if [ ! -s "$NOTES_FILE" ]; then
  printf '_No notable changes recorded for this release._\n\n' >> "$NOTES_FILE"
fi

if [ -n "$PREV_TAG" ] && [ -n "$REPO_URL" ]; then
  printf '**Full changelog:** %s/compare/%s...%s\n' "$REPO_URL" "$PREV_TAG" "$CURRENT_TAG" >> "$NOTES_FILE"
fi

# --- Expose notes to the workflow.
{
  echo "notes<<__KYOTO_NOTES_EOF__"
  cat "$NOTES_FILE"
  echo "__KYOTO_NOTES_EOF__"
} >> "${GITHUB_OUTPUT:-/dev/stdout}"

# --- Maintain CHANGELOG.md (prepend the new dated section).
SECTION_FILE="$(mktemp)"
{
  printf '## [%s] - %s\n\n' "$VERSION" "$DATE"
  cat "$NOTES_FILE"
  printf '\n'
} > "$SECTION_FILE"

if [ -f CHANGELOG.md ]; then
  ln="$(grep -n -m1 '^## \[' CHANGELOG.md | cut -d: -f1 || true)"
  if [ -n "$ln" ]; then
    head -n "$((ln - 1))" CHANGELOG.md > CHANGELOG.new
    cat "$SECTION_FILE" >> CHANGELOG.new
    tail -n "+${ln}" CHANGELOG.md >> CHANGELOG.new
  else
    cat CHANGELOG.md > CHANGELOG.new
    printf '\n' >> CHANGELOG.new
    cat "$SECTION_FILE" >> CHANGELOG.new
  fi
  mv CHANGELOG.new CHANGELOG.md
else
  {
    printf '# Changelog\n\n'
    printf 'All notable changes to this project are documented here.\n'
    printf 'This file is generated from commit history on each release.\n\n'
    cat "$SECTION_FILE"
  } > CHANGELOG.md
fi

echo "Generated notes for ${CURRENT_TAG} (range: ${RANGE}, ${#COMMITS[@]} commits)."
