# milon-export

milon ME (gym circle training) has no export. This project gets milon trainings onto Strava and Garmin Connect as strength activities with one set per station round (exercise, reps, weight). Strava builds its muscle map from the sets.

- Browser extension: on milonme.com, send a training to the Strava upload page, prefilled.
- Command-line tool: exports milon data to JSON, builds FIT files, uploads them to Garmin Connect, which forwards them to Strava.

Not affiliated with milon, Strava or Garmin. The milon web API and the `garminconnect` library are unofficial and can break without notice.

## Browser extension

Sends a milon ME training to the Strava upload page with the FIT file, title and per-station description filled in. Nothing is saved to Strava until Save is clicked.

### Install

| Browser | Steps |
|---|---|
| Firefox 140+ | Download the `.xpi` from the [latest release](https://github.com/0xbaa/milon2fit/releases/latest). Open it from the download panel, or `about:addons`, gear menu, Install Add-on From File. Updates install automatically. Clicking the `.xpi` link on GitHub may install it directly. |
| Chrome | Download `milon_to_strava-X.Y.Z.zip` from the latest release (not "Source code (zip)") and unzip it. Open `chrome://extensions`, enable Developer mode, click Load unpacked, pick the unzipped folder. Updates are manual. |

### Usage

1. Log in at https://www.milonme.com and at https://www.strava.com in the same browser.
2. On milonme.com click "milon → Strava" (bottom right). The panel lists trainings, newest first.
3. Click "Strava". The Strava upload page opens, the file is uploaded, title and description are filled, and the training is marked "sent".
4. Review the form, click Save on Strava.
5. "FIT" downloads the file for a manual Garmin Connect or Strava upload.

- Strava reports a training uploaded twice as a duplicate (matched by start time).
- Errors appear as one line in the panel or in a banner on the Strava page.

### Privacy

- The extension runs only in the browser, on `www.milonme.com` and `www.strava.com/upload/select`.
- No server, no analytics. No credentials leave the browser; it uses the existing milon and Strava sessions.

### Limits

- A change to the Strava upload page can break the prefill.
- The user clicks Save; the extension never saves.

## Command-line tool

### Requirements

- nix with flakes; `nix develop` provides python, uv, ruff, just, jq, nodejs, biome.
- direnv (optional): `.envrc` runs `use flake`.
- A password source for Garmin: a command such as `pass show garmin.com`, or the plaintext password.

### Setup

1. Enter the environment: `nix develop`, or `direnv allow`.
2. milon cookies:
   - Log in at https://www.milonme.com in a browser.
   - Export the cookies of `www.milonme.com` in Netscape format (a "cookies.txt" browser extension) to `auth/cookies-milonme-com.txt`.
   - The `rs-token` session lasts about 90 days. Re-export the file on HTTP 401.
3. Garmin Connect:
   - Create a free account at https://connect.garmin.com (no Garmin device needed).
   - Link Strava: Garmin Connect, Settings, Connected Apps, Strava. Activities uploaded to Garmin are then forwarded to Strava.
4. Configuration: `cp .env.example .env` and edit. The justfile loads `.env` (`set dotenv-load`).

   | Variable | Meaning |
   |---|---|
   | `GARMIN_EMAIL` | Garmin account email |
   | `GARMIN_PASSWORD_COMMAND` | Command whose first stdout line is the password, e.g. `pass show garmin.com`. Split with `shlex`, run without a shell. |
   | `GARMIN_PASSWORD` | Plaintext password |
   | `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` | Strava API path only (see Alternatives) |

   - Exactly one of `GARMIN_PASSWORD_COMMAND` and `GARMIN_PASSWORD` must be set; otherwise the login fails.
   - Values containing spaces must be double-quoted, e.g. `GARMIN_PASSWORD_COMMAND="pass show garmin.com"`.
5. Run `just garmin-login` in a terminal. It prompts for the MFA code if enabled. Tokens are saved to `~/.local/state/milon-export/garmin/`, outside the repo.
6. `just garmin` uses only the saved tokens. On auth errors run `just garmin-login` again.

### Usage

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
- `data/`, `auth/`, `state/`, `.env` and `cookies*.txt` are gitignored.

### Re-upload

- Delete the training on Garmin Connect, remove its `<t>` entry from `state/garmin-uploaded.json`, run `just garmin`.
- A training still present on Garmin is reported as a duplicate; its id is looked up and name and description are set again, but Garmin does not forward it to Strava again.
- Strava de-duplicates by start time, also against deleted activities: a training that was on Strava once is not accepted again via Garmin. Workaround: re-upload with all timestamps shifted by 60 s.

### What shows where

| | Garmin Connect | Strava (via Garmin) |
|---|---|---|
| Title | `Boomer Pump Circuit` (`ACTIVITY_NAME` in `src/milon_export/describe.py`) | Strava default, e.g. "Lunch Weight Training" |
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

- The milon API and `garminconnect` are unofficial; either may change and break the tool.
- Only premium circle trainings (`p` attendance); other types are skipped with a warning.
- milon provides no per-rep or heart-rate series; the FIT file has sets and laps only.
- Timestamps are UTC epochs. Only the month bucketing of attendance uses `Europe/Zurich` (`GYM_TZ`).
- Machine to FIT exercise mapping is `src/milon_export/exercise_rules.json` (read by `fit.py` and `js/fit.js`): ordered keyword rules on the machine name, first match wins; unmatched machines use category `unknown`.
- The "t moved" figure is the concentric volume (sum of average weight times moves); it is not verified against milon's own counter.

## Development

- `npm ci` installs JS dependencies once.
- `just check` runs ruff format, ruff check, biome format, biome lint, pytest and `node --test`. `just fmt-check` is the non-writing format check used in CI.
- Extension build:
  - `just ext-build`: bundles `js/milon.js` and `js/strava.js` into `extension/`, then `web-ext lint`.
  - `just ext-zip`: Chrome zip in `web-ext-artifacts/`.
  - `just ext-sign`: AMO unlisted signing, used by CI only.
  - Local run, after `just ext-build`: `npx web-ext run --source-dir extension` (Firefox) or load `extension/` unpacked (Chrome).

## Release (maintainer)

- One-time: create an AMO API key at addons.mozilla.org, Tools, Manage API Keys. Add repo secrets `WEB_EXT_API_KEY` (JWT issuer) and `WEB_EXT_API_SECRET`.
- The repo must be public: `gecko.update_url` in `extension/manifest.json` points to `https://github.com/0xbaa/milon2fit/releases/latest/download/updates.json`. Change it if the repo path differs.
- Bump `version` in `extension/manifest.json` (the only place the extension version lives), commit, then `git tag vX.Y.Z` and `git push --tags`.
- A release that fails after signing needs a version bump and a new tag, because AMO rejects a version it has already signed.
- `.github/workflows/release.yml` checks tag against manifest, runs `just fmt-check lint test`, builds, signs with AMO, and creates the GitHub release with the `.xpi`, the Chrome zip and `updates.json`.

## License

MIT, see `LICENSE`.
