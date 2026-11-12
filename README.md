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
  - Export the cookies of `www.milonme.com` in Netscape format (a "cookies.txt" browser extension) to `cookies-milonme-com.txt` in the repo root.
  - The `rs-token` session lasts about 90 days. Re-export the file on HTTP 401.
- Strava:
  - Create an app at https://www.strava.com/settings/api with Authorization Callback Domain `localhost`.
  - Put `STRAVA_CLIENT_ID` and `STRAVA_CLIENT_SECRET` in `.env`.
  - Run `just strava-auth`, open the printed URL, approve, then paste the redirected `http://localhost/?code=...` URL. The page does not load; that is expected.
  - The token is saved to `auth/strava-token.json` (mode 0600) and refreshed automatically.

## Usage

| Command | Effect |
|---|---|
| `just export` | Fetches profile, devices and monthly premium stats into `data/milon/` |
| `just upload --dry-run` | Writes FIT files to `data/fit/<t>.fit`, prints activity name and description |
| `just upload` | Uploads pending trainings to Strava |

- `data/`, `auth/`, `state/`, `.env` and `cookies*.txt` are gitignored.
- `state/strava-uploaded.json` maps training start time to Strava activity id. Trainings listed there are skipped.
- Re-uploading a training produces an identical FIT file, which Strava rejects as a duplicate; the error records the existing activity id. `external_id` (`milon-<t>.fit`) is only stored.

## Limits

- Only premium circle trainings (`p` attendance); other types are skipped with a warning.
- milon provides no per-rep or heart-rate series; the FIT file has sets and laps only.
- Timestamps are UTC epochs. Only the month bucketing of attendance uses `Europe/Zurich` (`GYM_TZ`).
- Station to FIT exercise mapping is the `EXERCISES` dict in `src/milon_export/fit.py`; unmapped stations use category `unknown`.
- The "t moved" figure is the concentric volume (sum of average weight times moves); it is not verified against milon's own counter.

## Development

- `just check` runs ruff format, ruff check and pytest.
