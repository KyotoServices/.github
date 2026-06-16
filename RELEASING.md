# Releasing Kyoto projects

This document describes how CI and releases work across every Kyoto repo
(KyotoCore, KyotoPractice, KyotoLobby-MC, KyotoProxy-MC, KyotoSurvivalGames-MC,
Kyoto-API, KyotoBot, CheatBreaker, and the `Web-*` projects) and how to cut a
new release — manually or automatically.

## How it works

All build logic lives **once** in this repo (`KyotoServices/.github`) as reusable
workflows under [`.github/workflows/`](.github/workflows) plus a composite
[`actions/changelog`](actions/changelog) action. Every project carries only two
thin caller workflows:

| File | Trigger | What it does |
|------|---------|--------------|
| `.github/workflows/ci.yml` | push / PR to the default branch | Builds (and tests where applicable) to catch breakage |
| `.github/workflows/release.yml` | push tag `v*` **or** manual dispatch | Builds the artifact, generates patch notes, opens a **draft** GitHub Release |

Archetypes: `gradle-{ci,release}` (plugins + API + bot), `angular-{ci,release}`
(web apps), `node-lib-{ci,release}` (Web-Shared), `static-release` (Web-TebexStore).

Releases are always created as **drafts** — review the notes and assets, then
click **Publish** in the GitHub Releases UI.

## Versioning

- Tag format: **`vMAJOR.MINOR.PATCH[-prerelease]`**, e.g. `v1.0.1-beta.1`.
  Use the dotted `-beta.N` form (matches `1.0.0-beta.1`), not `-beta1`.
- The tag is the source of truth: the release build injects the tag's version
  into the artifact, so the published jar/zip always matches the tag.
- The in-repo "baseline" version should be kept in sync with the latest tag so
  dev builds and `deploy_dev.py` report the right number. Where it lives:
  - **KyotoCore** → `gradle.properties` (`version=...`)
  - **Other Gradle repos** → `build.gradle.kts` (`version = (... releaseVersion ...) ?: "X"`)
  - **Web apps / Web-Shared** → `package.json` (+ `package-lock.json`)
  - **Web-TebexStore** → no version file (static site); tag only.

## Cutting a release — manual (per repo)

1. Bump the baseline version (see locations above). For web: `npm version 1.0.1-beta.1 --no-git-tag-version`.
2. Commit and push the bump to the default branch.
3. Tag and push:
   ```bash
   git tag -a v1.0.1-beta.1 -m "Release 1.0.1-beta.1"
   git push origin v1.0.1-beta.1
   ```
4. The **Release** workflow runs, builds, and opens a draft Release with notes +
   artifact. Review and **Publish**.

### Without a tag (manual dispatch)
Actions tab → **Release** → **Run workflow** → enter the version (e.g.
`1.0.1-beta.1`). Same result; the tag is created when the release is published.

## Cutting a release — all repos at once

From the monorepo checkout root (the folder that holds every repo), bump versions,
commit, then tag + push every repo. Example for the Gradle + web split used in
`1.0.1-beta.1` (adapt the version):

```bash
TAG=v1.0.1-beta.1
for d in KyotoCore KyotoPractice KyotoLobby-MC KyotoProxy-MC KyotoSurvivalGames-MC \
         CheatBreaker Kyoto-API KyotoBot Web-AdminPanel Web-CompanyHome \
         Web-StatsLeaderboard Web-StatusPage Web-Shared Web-TebexStore; do
  git -C "$d" tag -a "$TAG" -m "Release ${TAG#v}" && git -C "$d" push origin "$TAG"
done
```

> Tip: `pull-all.ps1` already iterates every repo subfolder — the same pattern
> works for a scripted tag-and-push.

## Patch notes — how they're generated

[`gen-notes.sh`](actions/changelog/gen-notes.sh) collects commits since the
previous tag and buckets them by the **leading verb** of each commit subject
(the imperative style used here), with Security/Dependencies detected by content:

| Section | Matches (leading verb / content) |
|---------|----------------------------------|
| **Added** | Add, Introduce, Implement, Create, Support, Enable, Expose, Persist, Track |
| **Fixed** | Fix, Resolve, Correct, Patch, Repair, Prevent |
| **Changed** | Change, Update, Improve, Enhance, Refactor, Rework, Rename, Move, Adjust, Tune, Tweak, Expand, Simplify, Revert, Round, Clarify, Migrate |
| **Removed** | Remove, Delete, Drop, Strip, Prune, Disable |
| **Security** | subject contains `secur`, `vuln`, `cve`, `secret`, `harden`, `exploit`, `sign…` |
| **Dependencies** | Bump, Upgrade, or any commit authored by `dependabot[bot]` |
| **Other** | anything unmatched |

A `CHANGELOG.md` section is also generated and attached to the release. To tune
the buckets, edit the keyword lists in `gen-notes.sh` — write commit subjects in
imperative mood ("Add X", "Fix Y") for the cleanest notes.

## One-time setup / prerequisites

These are configured in the GitHub UI, not in files:

1. **Reusable-workflow access** — this repo (`.github`) → Settings → Actions →
   General → **Access** = *Accessible from repositories owned by the
   organization*. This makes both the reusable workflows and the changelog action
   reachable from every repo. (Already enabled.)

2. **`SIBLING_TOKEN` org secret** — required by the repos that check out a second
   **private** repo during their build, because the default `GITHUB_TOKEN` cannot
   clone other private repos:
   - **CheatBreaker** → needs `KyotoCore-MC` (`includeBuild("../KyotoCore")`)
   - **Web-AdminPanel, Web-CompanyHome, Web-StatsLeaderboard** → need `Web-Shared`
     (`@kyoto/ui` = `file:../Web-Shared`)

   Create a fine-grained PAT (or GitHub App token) with **read** access to
   `KyotoCore-MC` and `Web-Shared`, then add it as an **organization** Actions
   secret named `SIBLING_TOKEN`:
   ```bash
   gh secret set SIBLING_TOKEN --org KyotoServices --app actions \
     --visibility all --body '<TOKEN>'
   ```
   The reusable workflows fall back to `GITHUB_TOKEN` when the secret is absent,
   so the other 10 repos build without it. Until `SIBLING_TOKEN` exists, CI and
   release runs for those 4 repos fail at the sibling-checkout step.

## Troubleshooting

- **`Not Found - .../repos#get-a-repository`** at a checkout step → `SIBLING_TOKEN`
  is missing or lacks read access to the sibling repo (see setup #2).
- **`workflow was not found` / access denied** resolving a reusable workflow →
  the `.github` Actions access setting (setup #1) is off.
- **Release ran but no draft appeared** → check the run's "Create draft release"
  step; `contents: write` permission must be allowed by org/repo policy.
- **Re-run a failed release after fixing setup** → Actions tab → the failed
  **Release** run → **Re-run jobs** (the tag already exists), or delete and
  re-push the tag.
- **Wrong bucket in notes** → adjust keyword lists in `gen-notes.sh`.
- **Need a release for a sibling-dependent repo before `SIBLING_TOKEN` exists**
  → build locally (the sibling repos are checked out next to it) and publish by
  hand, e.g. `./gradlew shadowJar -PreleaseVersion=X` or `npm run build`, then
  `gh release create vX -R KyotoServices/<repo> --draft --prerelease <artifact>`.
  This is a stopgap; add `SIBLING_TOKEN` so CI does it automatically.
