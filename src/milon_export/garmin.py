import logging
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path

from garminconnect import Garmin
from garminconnect.exceptions import GarminConnectConnectionError

GARMIN_DIR = Path("auth/garmin")
PASS_ENTRY = "garmin.com"
LOOKUP_ATTEMPTS = 10
LOOKUP_INTERVAL = 3
START_TOLERANCE = 1
GMT_FORMAT = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger("milon")


def parse_upload_result(payload: dict) -> int | None:
    """Activity id of a finished upload; None if Garmin accepted it for processing."""
    result = payload["detailedImportResult"]
    if result["successes"]:
        return result["successes"][0]["internalId"]
    if result["failures"]:
        messages = result["failures"][0]["messages"]
        raise RuntimeError(f"garmin upload failed: {[m['content'] for m in messages]}")
    return None


def find_activity_id(activities: list[dict], start: int) -> int | None:
    for act in activities:
        gmt = datetime.strptime(act["startTimeGMT"], GMT_FORMAT).replace(tzinfo=UTC)
        if abs(gmt.timestamp() - start) <= START_TOLERANCE:
            return act["activityId"]
    return None


def wait_for_activity(api: Garmin, start: int) -> int:
    """Find the activity starting at epoch `start`, retrying while Garmin processes."""
    day = datetime.fromtimestamp(start, UTC).date()
    first, last = (day + timedelta(days=d) for d in (-1, 1))
    for attempt in range(LOOKUP_ATTEMPTS):
        if attempt:
            time.sleep(LOOKUP_INTERVAL)
        activities = api.get_activities_by_date(first.isoformat(), last.isoformat())
        if (activity_id := find_activity_id(activities, start)) is not None:
            return activity_id
    raise RuntimeError(f"garmin activity starting at {start} not found")


def pass_secret(entry: str) -> str:
    """First line of `pass show <entry>` (password-store convention)."""
    out = subprocess.run(
        ["pass", "show", entry], stdout=subprocess.PIPE, text=True, check=True
    )
    return out.stdout.splitlines()[0]


def login() -> Garmin:
    """Credential login (GARMIN_EMAIL + `pass` password, MFA prompt); saves tokens."""
    api = Garmin(
        os.environ["GARMIN_EMAIL"],
        pass_secret(PASS_ENTRY),
        prompt_mfa=lambda: input("Garmin MFA code: "),
    )
    api.login(str(GARMIN_DIR))
    save_tokens(api)
    return api


def connect() -> Garmin:
    """Log in with the tokens saved by `login`."""
    api = Garmin()
    api.login(str(GARMIN_DIR))
    save_tokens(api)
    return api


def save_tokens(api: Garmin) -> None:
    # The lib swallows dump errors during login, so dump explicitly.
    api.client.dump(str(GARMIN_DIR))


def upload_fit_file(api: Garmin, path: Path, start: int) -> int:
    """Upload a FIT file; returns the Garmin activity id (existing one on duplicate)."""
    try:
        payload = api.upload_activity(str(path))
    except GarminConnectConnectionError as e:
        if e.response is None or e.response.status_code != HTTPStatus.CONFLICT:
            raise
        log.warning("%s already on garmin, looking up its id", path.name)
        return wait_for_activity(api, start)
    activity_id = parse_upload_result(payload)
    return wait_for_activity(api, start) if activity_id is None else activity_id
