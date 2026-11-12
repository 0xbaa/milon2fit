export:
    uv run milon export

strava-auth:
    uv run milon strava-auth

upload *args:
    uv run milon upload {{args}}

fmt:
    ruff format .

lint:
    ruff check .

test:
    uv run pytest

check: fmt lint test
