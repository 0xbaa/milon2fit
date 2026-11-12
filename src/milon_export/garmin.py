import os
from dataclasses import dataclass
from pathlib import Path

from garminconnect import Garmin
from garminconnect.exceptions import GarminConnectConnectionError

GARMIN_DIR = Path("auth/garmin")
TOKEN_FILE = GARMIN_DIR / "garmin_tokens.json"
HTTP_CONFLICT = 409
DUPLICATE_CODE = 202


@dataclass(frozen=True)
class UploadOutcome:
    activity_id: int | None
    duplicate: bool


def parse_upload_result(payload: dict) -> UploadOutcome:
    """Interpret a Garmin `detailedImportResult` upload response."""
    result = payload["detailedImportResult"]
    if result["successes"]:
        return UploadOutcome(result["successes"][0]["internalId"], duplicate=False)
    if not result["failures"]:
        raise RuntimeError("garmin upload returned neither successes nor failures")
    failure = result["failures"][0]
    messages = failure["messages"]
    if any(m["code"] == DUPLICATE_CODE for m in messages):
        return UploadOutcome(failure.get("internalId"), duplicate=True)
    raise RuntimeError(f"garmin upload failed: {[m['content'] for m in messages]}")


def connect() -> Garmin:
    """Log in with saved tokens, else GARMIN_EMAIL/GARMIN_PASSWORD (MFA prompt).

    Tokens are persisted in `auth/garmin/` (mode 0700).
    """
    GARMIN_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    GARMIN_DIR.chmod(0o700)
    if TOKEN_FILE.exists():
        email = password = None
    else:
        email, password = os.environ["GARMIN_EMAIL"], os.environ["GARMIN_PASSWORD"]
    api = Garmin(email, password, prompt_mfa=lambda: input("Garmin MFA code: "))
    api.login(str(GARMIN_DIR))
    api.client.dump(str(GARMIN_DIR))
    return api


def upload_fit_file(api: Garmin, path: Path) -> UploadOutcome:
    try:
        payload = api.upload_activity(str(path))
    except GarminConnectConnectionError as e:
        if e.response is None or e.response.status_code != HTTP_CONFLICT:
            raise
        payload = e.response.json()
    return parse_upload_result(payload)
