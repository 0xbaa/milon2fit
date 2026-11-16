export:
    uv run milon export

strava-auth:
    uv run milon strava-auth

upload *args:
    uv run milon upload {{args}}

garmin-login:
    uv run milon garmin-login

garmin *args:
    uv run milon garmin {{args}}

fmt-check:
    ruff format --check .
    biome format js

fmt:
    ruff format .
    biome format --write js

lint:
    ruff check .
    biome lint js

test:
    uv run pytest
    TZ=Europe/Zurich node --test 'js/*.test.js'

check: fmt lint test

ext-build:
    npx --no-install esbuild js/milon.js js/strava.js --bundle --format=iife --outdir=extension
    npx --no-install web-ext lint --self-hosted --source-dir extension

ext-zip: ext-build
    npx --no-install web-ext build --source-dir extension --overwrite-dest

# Used by CI (release.yml); needs WEB_EXT_API_KEY and WEB_EXT_API_SECRET.
ext-sign *args: ext-build
    npx --no-install web-ext sign --source-dir extension --channel unlisted {{args}}
