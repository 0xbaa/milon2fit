# milon-export

- Exports milon ME gym training data (premium circle trainings) to JSON.
- Uploads each training to Strava as a FIT file (sport training, sub-sport strength training, one set per station round).

## Requirements

- nix with flakes; `nix develop` provides python, uv, ruff, just, jq.
- direnv (optional): `.envrc` runs `use flake` and loads `.env`.

## Setup

- Enter the environment: `nix develop`, or `direnv allow`.
- milon cookies:
  - Log in at https://www.milonme.com in a browser.
  - Export the cookies of `www.milonme.com` in Netscape format (a "cookies.txt" browser extension) to `auth/cookies-milonme-com.txt`.
  - The `rs-token` session lasts about 90 days. Re-export the file on HTTP 401.
- Strava:
  - Create an app at https://www.strava.com/settings/api with Authorization Callback Domain `localhost`.
  - Put `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in `.env`.
  - Run `just strava-auth`, open the printed URL, approve, then paste the redirected `http://localhost/?code=...` URL. The page does not load; that is expected.
  - The token is saved to `auth/strava-token.json` (mode 0600) and refreshed automatically.

- Garmin (alternative to the Strava API, which needs a subscription):
  - Free Garmin Connect account. In Garmin Connect, link Strava under Connected Apps; activities uploaded to Garmin then sync to Strava.
  - Put `GARMIN_EMAIL` in `.env`. The password is read from `pass show garmin.com` (first line). Both are only needed until tokens are saved.
  - Run `just garmin-login` once, interactively (prompts for the MFA code if enabled). Tokens are saved to `auth/garmin/` (mode 0700).
  - Uses the unofficial `garminconnect` library; Garmin may change the API and break it.

## Usage

| Command | Effect |
|---|---|
| `just export` | Fetches profile, devices and monthly premium stats into `data/milon/` |
| `just upload --dry-run` | Writes FIT files to `data/fit/<t>.fit`, prints activity name and description |
| `just upload` | Uploads pending trainings to Strava |
| `just garmin --dry-run` | Writes FIT files, prints activity name and description, no login |
| `just garmin` | Uploads pending trainings to Garmin Connect, then sets name and description |

- `data/`, `auth/`, `state/`, `.env` and `cookies*.txt` are gitignored.
- `state/strava-uploaded.json` maps training start time to Strava activity id. Trainings listed there are skipped.
- `state/garmin-uploaded.json` maps training start time to Garmin activity id (null when a duplicate response gave no id).
- While `fit.py` is unchanged, re-uploading a training produces an identical FIT file, which Strava rejects as a duplicate; the error records the existing activity id. `external_id` (`milon-<t>.fit`) is only stored.

## Limits

- Only premium circle trainings (`p` attendance); other types are skipped with a warning.
- milon provides no per-rep or heart-rate series; the FIT file has sets and laps only.
- Timestamps are UTC epochs. Only the month bucketing of attendance uses `Europe/Zurich` (`GYM_TZ`).
- Station to FIT exercise mapping is the `EXERCISES` dict in `src/milon_export/fit.py`; unmapped stations use category `unknown`.
- The "t moved" figure is the concentric volume (sum of average weight times moves); it is not verified against milon's own counter.

## Development

- `just check` runs ruff format, ruff check and pytest.
