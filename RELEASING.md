# Releasing & deploying Kyoto projects

This document describes how CI, releases, and **deploys (CD)** work across every
Kyoto repo (KyotoCore, KyotoPractice, KyotoLobby-MC, KyotoProxy-MC,
KyotoSurvivalGames-MC, Kyoto-API, KyotoBot, CheatBreaker, and the `Web-*`
projects) and how to cut a new release and ship it.

**The whole pathway at a glance:**

```
push tag vX.Y.Z  →  CI builds  →  draft GitHub Release (artifact + patch notes)
       │
       └─ you review & click Publish   ←── this is the deploy gate
                    │
       release published  →  Deploy auto-runs on the self-hosted org runner
                              →  uploads the artifact to the dev servers, restarts, verifies
```

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

## Deploying (CD)

Once a release is **Published**, its artifact is shipped to the servers
automatically. Cloud runners can't reach the `10.147.18.x` network, so deploys
run on a **self-hosted runner** (`kyoto-dev-us`, org-level, on dev-us) — it's the
"build server". The deploy logic lives once in this repo under
[`deploy/`](deploy) + the reusable workflows below; each project has a thin
[`deploy.yml`](../KyotoSurvivalGames-MC/.github/workflows/deploy.yml) caller.

**Triggers** (every `deploy.yml`):
- `release: { types: [published] }` — **auto-deploys on Publish.** Because releases
  are created as drafts, *publishing* is the deliberate human step, i.e. the gate.
- `workflow_dispatch` — manual: Actions → **Deploy** → Run workflow → enter the tag
  (`gh workflow run deploy.yml -R KyotoServices/<repo> -f tag=vX.Y.Z`).

> **Why publish = gate:** enforced Environment *required-reviewer* approvals need a
> paid plan for private repos, so on Free the Publish click is the approval. To add
> a real popup approval later: upgrade plan → set required reviewers on the `dev`
> (and `production`) environment.

**Archetypes** (reusable workflows in [`.github/workflows/`](.github/workflows)):

| Archetype | Workflow | Deploys | Verifies |
|-----------|----------|---------|----------|
| Paper / Velocity plugins | `deploy-pelican.yml` | jar → Pelican `plugins/` (uploads, backs up old, restarts container) | `Enabling <plugin>` (Paper) / `Loaded plugin <name>` (Velocity) in `latest.log` |
| systemd services | `deploy-service.yml` | installDist `.tar.gz` → extract/sync + `systemctl restart` | `is-active` + HTTP liveness or a "ready" log line |
| static sites | `deploy-web.yml` | site `.zip` → `/var/www/<domain>` + `nginx -t` && reload | optional curl |

- **Fan-out:** `deploy-pelican.yml` takes a `targets` JSON array, so one deploy hits
  many stacks — **KyotoCore** → lobby + practice + survivalgames; **CheatBreaker** →
  both lobbies + survivalgames + practice. Container short-ids are resolved live by
  Pelican UUID (stable), with a hardcoded fallback.
- **Per-component targets** (host + Pelican UUID + log path) live in each repo's
  `deploy.yml`. The host/UUID map is in the root `CLAUDE.md`.
- **No CD:** Web-TebexStore (manual panel paste) and Web-Shared (library).

**Credentials & rollback:**
- SSH creds live **only on the runner** at `/opt/kyoto-deploy/creds.md` (root 600) —
  never in GitHub. The `.github` repo is **public**, so its `deploy/` tooling must
  stay generic (no IPs/UUIDs/creds; those come from the private per-repo callers).
- Every deploy backs up what it replaces (`.bak-<timestamp>`). Roll back by running
  the relevant script with `--rollback` on the runner, e.g.
  `KYOTO_CREDS_FILE=/opt/kyoto-deploy/creds.md python3 /opt/kyoto-deploy/deploy_artifact.py --plugin-name KyotoCore --targets '<json>' --rollback`.

**Going to production:** dev is the live stand-in today. When prod exists (also
Pelican), add a `production` environment + the live host/UUIDs to each `deploy.yml`
caller — no tooling changes. Updating the deploy scripts means editing
`.github/deploy/*.py` **and** re-copying them to the runner's `/opt/kyoto-deploy/`.

### Deploy prerequisites (one-time)
- Self-hosted runner `kyoto-dev-us` registered **org-level** (Default group) with
  label `kyoto-deploy`, running as a service on dev-us (`/opt/actions-runner`).
  (Org runner registration needs `admin:org` → done via the GitHub UI, since `gh`
  here lacks that scope. Custom runner *groups* need a paid plan; the Default group
  is fine on Free.)
- `python3-paramiko` installed on the runner; `/opt/kyoto-deploy/` holds the deploy
  scripts + `creds.md`.

## One-time setup / prerequisites

These are configured in the GitHub UI, not in files:

1. **Reusable-workflow access** — this repo (`.github`) → Settings → Actions →
   General → **Access** = *Accessible from repositories owned by the
   organization*. This makes both the reusable workflows and the changelog action
   reachable from every repo. (Already enabled.)

2. **`SIBLING_TOKEN` secret** — required by the repos that check out a second
   **private** repo during their build, because the default `GITHUB_TOKEN` cannot
   clone other private repos:
   - **CheatBreaker** → needs `KyotoCore-MC` (`includeBuild("../KyotoCore")`)
   - **Web-AdminPanel, Web-CompanyHome, Web-StatsLeaderboard** → need `Web-Shared`
     (`@kyoto/ui` = `file:../Web-Shared`)

   > **Plan note:** organization-level Actions secrets **cannot be used by private
   > repos on the Free plan**, so `SIBLING_TOKEN` is set as a **per-repo** secret
   > on those 4 repos (not org-wide). It currently holds a fine-grained PAT
   > **`kyoto-ci-sibling-read`** (resource owner `KyotoServices`, Contents+Metadata
   > read-only on `KyotoCore-MC` + `Web-Shared`) that **expires `2026-07-16`** —
   > regenerate it and re-set the 4 secrets before then or those CI/deploy runs break.

   ```bash
   # per-repo (Free plan):
   for r in CheatBreaker Web-AdminPanel Web-CompanyHome Web-StatsLeaderboard; do
     echo '<TOKEN>' | gh secret set SIBLING_TOKEN -R KyotoServices/$r
   done
   # on a paid plan you could instead use one org secret (visibility = all repos).
   ```
   The reusable workflows fall back to `GITHUB_TOKEN` when the secret is absent,
   so the other repos build without it.

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
- **Deploy didn't auto-start after publishing** → the `release` event only fires on a
  genuine draft→publish (or creating a published release). Toggling an already-published
  release's draft flag via API does **not** re-emit it — use `workflow_dispatch` instead,
  or cut a new release.
- **Deploy queued forever / "no runner"** → the self-hosted runner is offline. On dev-us:
  `systemctl status 'actions.runner.*'`. It must be online with the `kyoto-deploy` label.
- **Deploy fails at "Download release jar/tarball/zip"** → the published release has no
  matching asset (jar / `.tar.gz` / `.zip`) — re-run the **Release** workflow first.
- **`ModuleNotFoundError: paramiko` on the runner** → `apt-get install -y python3-paramiko`.
- **Need a release for a sibling-dependent repo before `SIBLING_TOKEN` exists**
  → build locally (the sibling repos are checked out next to it) and publish by
  hand, e.g. `./gradlew shadowJar -PreleaseVersion=X` or `npm run build`, then
  `gh release create vX -R KyotoServices/<repo> --draft --prerelease <artifact>`.
  This is a stopgap; add `SIBLING_TOKEN` so CI does it automatically.
