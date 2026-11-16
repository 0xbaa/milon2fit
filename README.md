# milon-export

- Exports milon ME gym training data (premium circle trainings) to JSON.
- Converts each training to a FIT strength activity: sport training, sub-sport strength training, one set per station round with exercise, reps and weight.
- Uploads the FIT files to Garmin Connect, which syncs them to Strava. Strava builds its muscle map from the sets.

## Requirements

- nix with flakes; `nix develop` provides python, uv, ruff, just, jq, nodejs, biome.
- direnv (optional): `.envrc` runs `use flake` and loads `.env`.
- `pass` (password-store) with an entry `garmin.com` whose first line is the Garmin password.

## Setup

1. Enter the environment: `nix develop`, or `direnv allow`.
2. milon cookies:
   - Log in at https://www.milonme.com in a browser.
   - Export the cookies of `www.milonme.com` in Netscape format (a "cookies.txt" browser extension) to `auth/cookies-milonme-com.txt`.
   - The `rs-token` session lasts about 90 days. Re-export the file on HTTP 401.
3. Garmin Connect:
   - Create a free account at https://connect.garmin.com (no Garmin device needed).
   - Link Strava: Garmin Connect, Settings, Connected Apps, Strava. Activities uploaded to Garmin are then forwarded to Strava.
   - Put `GARMIN_EMAIL=...` in `.env`.
   - Run `just garmin-login` in a terminal. It reads the password via `pass show garmin.com` and prompts for the MFA code if enabled. Tokens are saved to `~/.local/state/milon-export/garmin/`, outside the repo, so a sandboxed Claude Code session in this repo cannot read them.
   - `just garmin` uses only the saved tokens. On auth errors run `just garmin-login` again.

## Usage

After each gym visit:

```
just export
just garmin
```

| Command | Effect |
|---|---|
| `just export` | Fetches profile, devices and monthly premium stats into `data/milon/` |
| `just garmin --dry-run` | Writes FIT files to `data/fit/<t>.fit`, prints activity name and description, no login |
| `just garmin` | Uploads pending trainings to Garmin Connect, then sets name and description |

- `<t>` is the training start as a Unix timestamp.
- `state/garmin-uploaded.json` maps `<t>` to the Garmin activity id. Trainings listed there are skipped.
- Re-upload a training: delete it on Garmin Connect, remove its `<t>` entry from `state/garmin-uploaded.json`, run `just garmin`. A training still present on Garmin is reported as a duplicate; its id is looked up and name and description are set again, but Garmin does not forward it to Strava again.
- Strava de-duplicates by start time, also against deleted activities: a training that was on Strava once is not accepted again via Garmin. Workaround used once: re-upload with all timestamps shifted by 60 s.
- `data/`, `auth/`, `state/`, `.env` and `cookies*.txt` are gitignored.

## What shows where

| | Garmin Connect | Strava (via Garmin) |
|---|---|---|
| Title | `Boomer Pump Circuit` (`ACTIVITY_NAME` in `describe.py`) | Strava default, e.g. "Lunch Weight Training" |
| Description | per-station summary | none (name and description are set on Garmin after the forward) |
| Sets, muscle map | yes | yes |
| Visibility | Garmin privacy setting | Strava default activity visibility (Settings, Privacy Controls) |

## Alternatives

- Manual Strava upload: `just garmin --dry-run`, then upload `data/fit/*.fit` at https://www.strava.com/upload/select and paste the printed description.
- Strava API (requires a Strava subscription for API access):
  - Create an app at https://www.strava.com/settings/api with Authorization Callback Domain `localhost`.
  - Put `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in `.env`.
  - Run `just strava-auth`, open the printed URL, approve, then paste the redirected `http://localhost/?code=...` URL. The page does not load; that is expected. The token is saved to `auth/strava-token.json` (mode 0600) and refreshed automatically.
  - `just upload [--dry-run]` uploads pending trainings and sets name, description and sport type. State is `state/strava-uploaded.json`. Strava rejects re-uploads of an identical FIT file as duplicates (identical while `fit.py` and the machine names in `devices.json` are unchanged); the error records the existing activity id.

## Limits

- Garmin upload uses the unofficial `garminconnect` library; Garmin may change its API and break it.
- Only premium circle trainings (`p` attendance); other types are skipped with a warning.
- milon provides no per-rep or heart-rate series; the FIT file has sets and laps only.
- Timestamps are UTC epochs. Only the month bucketing of attendance uses `Europe/Zurich` (`GYM_TZ`).
- Machine to FIT exercise mapping is `src/milon_export/exercise_rules.json` (read by `fit.py` and `js/fit.js`): ordered keyword rules on the machine name, first match wins; unmatched machines use category `unknown`.
- The "t moved" figure is the concentric volume (sum of average weight times moves); it is not verified against milon's own counter.

## Development

- `just check` runs ruff format, ruff check, biome format, biome lint, pytest and `node --test`. `just fmt-check` is the non-writing format check used in CI.
- `npm ci` installs JS dependencies once.

## Browser extension

Sends a milon ME training to the Strava upload page, prefilled with the FIT file, title and per-station description. Nothing is saved to Strava until Save is clicked.

### Install (friends)

- Firefox 140 or newer: open the latest release page, click the `.xpi` file, confirm. Updates install automatically via `updates.json`.
  - Fallback if Firefox downloads the file instead of installing: open the download panel and click the file, or `about:addons`, gear menu, Install Add-on From File.
  - Unconfirmed: verify the direct install on the first release.
- Chrome: download the `.zip` from the latest release and unzip it. Open `chrome://extensions`, enable Developer mode, click Load unpacked, pick the unzipped folder. Updates are manual.

### Usage

- Log in at www.milonme.com and at Strava in the same browser.
- On milonme.com click "milon → Strava" (bottom right). The panel lists trainings newest first.
- "Strava" opens the Strava upload page, uploads the file, fills title and description, and marks the training "sent". Review the form and click Save.
- "FIT" downloads the file for a manual Garmin Connect or Strava upload.
- Strava reports a training uploaded twice as a duplicate (matched by start time).
- Errors appear as one line in the panel or in a banner on the Strava page.

### Build

- `just ext-build`: bundles `js/milon.js` and `js/strava.js` into `extension/`, then `web-ext lint`.
- `just ext-zip`: Chrome zip in `web-ext-artifacts/`.
- `just ext-sign`: AMO unlisted signing, used by CI only; CI is the only signing path.
- Local run: `npx web-ext run --source-dir extension` (Firefox) or load `extension/` unpacked (Chrome).

### Release (maintainer)

- One-time: create an AMO API key at addons.mozilla.org, Tools, Manage API Keys. Add repo secrets `WEB_EXT_API_KEY` (JWT issuer) and `WEB_EXT_API_SECRET`.
- The repo must be public: `gecko.update_url` in `extension/manifest.json` points to `https://github.com/0xbaa/milon2fit/releases/latest/download/updates.json`. Change it if the repo path differs.
- Bump `version` in `extension/manifest.json` (the only place the version lives), commit, then `git tag vX.Y.Z` and `git push --tags`.
- A release that fails after signing needs a version bump and a new tag, because AMO rejects a version it has already signed.
- `.github/workflows/release.yml` checks tag against manifest, runs `just check`, builds, signs with AMO, and creates the GitHub release with the `.xpi`, the Chrome zip and `updates.json`.
