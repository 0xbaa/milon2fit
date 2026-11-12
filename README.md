# milon-export

- Exports milon ME gym training data (premium circle trainings) to JSON.
- Converts each training to a FIT strength activity: sport training, sub-sport strength training, one set per station round with exercise, reps and weight.
- Uploads the FIT files to Garmin Connect, which syncs them to Strava. Strava builds its muscle map from the sets.

## Requirements

- nix with flakes; `nix develop` provides python, uv, ruff, just, jq.
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
   - Run `just garmin-login` in a terminal. It reads the password via `pass show garmin.com` and prompts for the MFA code if enabled. Tokens are saved to `auth/garmin/`.
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
- `data/`, `auth/`, `state/`, `.env` and `cookies*.txt` are gitignored.

## What shows where

| | Garmin Connect | Strava (via Garmin, not yet verified) |
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
  - `just upload [--dry-run]` uploads pending trainings and sets name, description and sport type. State is `state/strava-uploaded.json`. Strava rejects re-uploads of an identical FIT file as duplicates (identical while `fit.py` is unchanged); the error records the existing activity id.

## Limits

- Garmin upload uses the unofficial `garminconnect` library; Garmin may change its API and break it.
- Only premium circle trainings (`p` attendance); other types are skipped with a warning.
- milon provides no per-rep or heart-rate series; the FIT file has sets and laps only.
- Timestamps are UTC epochs. Only the month bucketing of attendance uses `Europe/Zurich` (`GYM_TZ`).
- Station to FIT exercise mapping is the `EXERCISES` dict in `src/milon_export/fit.py`; unmapped stations use category `unknown`.
- The "t moved" figure is the concentric volume (sum of average weight times moves); it is not verified against milon's own counter.

## Development

- `just check` runs ruff format, ruff check and pytest.
