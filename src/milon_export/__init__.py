import argparse
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from milon_export.describe import ACTIVITY_NAME, build_description
from milon_export.fit import build_fit
from milon_export.garmin import connect, login, upload_fit_file
from milon_export.training import GYM_TZ, pending_trainings, training_window

log = logging.getLogger("milon")

API = "https://www.milonme.com/api/"
COOKIE_FILE = Path("auth/cookies-milonme-com.txt")
MILON_DIR = Path("data/milon")
TOKEN_FILE = Path("auth/strava-token.json")
UPLOADED_FILE = Path("state/strava-uploaded.json")
GARMIN_UPLOADED_FILE = Path("state/garmin-uploaded.json")
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API = "https://www.strava.com/api/v3/"
FIT_DIR = Path("data/fit")
UPLOAD_TIMEOUT = 120
POLL_INTERVAL = 2
TOKEN_EXPIRY_MARGIN = 60


def parse_cookies(text: str) -> dict[str, str]:
    """Netscape cookie file to name/value map (MozillaCookieJar drops `mf`)."""
    cookies = {}
    for line in text.splitlines():
        line = line.removeprefix("#HttpOnly_")
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            raise ValueError(f"expected 7 tab-separated fields, got {len(fields)}")
        cookies[fields[5]] = fields[6]
    return cookies


def attendance_months(attendance: list[dict]) -> list[str]:
    """Distinct YYMM (gym time) of premium ("p") attendance entries, sorted."""
    months = set()
    skipped = 0
    for entry in attendance:
        if entry["type"] != "p":
            skipped += 1
            continue
        months.add(datetime.fromtimestamp(entry["t"], GYM_TZ).strftime("%y%m"))
    if skipped:
        log.warning("skipped %d non-premium attendance entries", skipped)
    return sorted(months)


def duplicate_activity_id(error: str) -> int | None:
    match = re.search(r"duplicate of (?:activity |.*?activities/)(\d+)", error)
    return int(match.group(1)) if match else None


def token_expired(token: dict, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    return token["expires_at"] <= now + TOKEN_EXPIRY_MARGIN


def extract_code(pasted: str) -> str:
    pasted = pasted.strip()
    if not pasted.startswith("http"):
        return pasted
    query = parse_qs(urlparse(pasted).query)
    if "code" not in query:
        raise ValueError(f"no code in redirect URL, error={query.get('error')}")
    if "activity:write" not in query["scope"][0].split(","):
        raise ValueError("scope activity:write not granted")
    return query["code"][0]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text())


def check(resp: httpx.Response) -> httpx.Response:
    if resp.is_error:
        raise RuntimeError(f"{resp.status_code} {resp.request.url.path}: {resp.text}")
    return resp


def milon_get(client: httpx.Client, path: str):
    return check(client.get(path)).json()


def export() -> None:
    cookies = parse_cookies(COOKIE_FILE.read_text())
    with httpx.Client(base_url=API, cookies=cookies) as client:
        profile = milon_get(client, "user/profile")
        write_json(MILON_DIR / "profile.json", profile)
        sid, uid = profile["_sid"], profile["id"]
        home = milon_get(client, f"user/stats/home/{sid}/{uid}")
        write_json(MILON_DIR / "devices.json", milon_get(client, f"devices/{sid}"))
        log.info("exported profile and devices")
        for month in attendance_months(home["attendance"]):
            data = milon_get(client, f"user/stats/premium/{sid}/{uid}/{month}")
            write_json(MILON_DIR / f"premium-{month}.json", data)
            log.info("exported %s: %d trainings", month, len(data["stats"]))


def strava_auth() -> None:
    client_id = os.environ["STRAVA_CLIENT_ID"]
    client_secret = os.environ["STRAVA_CLIENT_SECRET"]
    params = httpx.QueryParams(
        client_id=client_id,
        redirect_uri="http://localhost",
        response_type="code",
        approval_prompt="force",
        scope="activity:write",
    )
    print(f"{STRAVA_AUTH_URL}?{params}")
    code = extract_code(input("Paste redirected URL or code: "))
    resp = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
    )
    check(resp)
    write_token(resp.json())
    log.info("saved %s", TOKEN_FILE)


def write_token(token: dict) -> None:
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TOKEN_FILE.with_suffix(".json.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(token, f, indent=2)
        f.write("\n")
    tmp.replace(TOKEN_FILE)


def fresh_token() -> str:
    token = read_json(TOKEN_FILE)
    if token_expired(token):
        resp = httpx.post(
            STRAVA_TOKEN_URL,
            data={
                "client_id": os.environ["STRAVA_CLIENT_ID"],
                "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
                "grant_type": "refresh_token",
                "refresh_token": token["refresh_token"],
            },
        )
        check(resp)
        token = resp.json()
        write_token(token)
        log.info("refreshed strava token")
    return token["access_token"]


def load_stats() -> list[dict]:
    stats = []
    for path in sorted(MILON_DIR.glob("premium-*.json")):
        stats.extend(read_json(path)["stats"])
    return sorted(stats, key=lambda s: s["training"]["t"])


def wait_for_upload(client: httpx.Client, upload_id: int) -> dict:
    deadline = time.monotonic() + UPLOAD_TIMEOUT
    while time.monotonic() < deadline:
        status = check(client.get(f"uploads/{upload_id}")).json()
        if status["activity_id"] or status["error"]:
            return status
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"strava upload {upload_id} still processing")


def upload_training(
    client: httpx.Client,
    stat: dict,
    devices_map: dict,
    stats: list[dict],
    uploaded: dict,
) -> None:
    """Upload one training as FIT and record its activity id in the state file.

    The id is written before the sport_type PUT so a failed PUT does not lose it.
    """
    t = stat["training"]["t"]
    resp = check(
        client.post(
            "uploads",
            files={"file": (f"milon-{t}.fit", build_fit(stat))},
            data={
                "data_type": "fit",
                "name": ACTIVITY_NAME,
                "description": build_description(stat, devices_map, stats),
                "trainer": 1,
                "external_id": f"milon-{t}.fit",
            },
        )
    )
    status = wait_for_upload(client, resp.json()["id"])
    existing = None
    if status["error"]:
        existing = duplicate_activity_id(status["error"])
        if existing is None:
            raise RuntimeError(f"strava upload of {t} failed: {status['error']}")
        log.warning("%s is a duplicate of strava activity %s", t, existing)
    activity_id = existing or status["activity_id"]
    uploaded[str(t)] = activity_id
    write_json(UPLOADED_FILE, uploaded)
    check(
        client.put(f"activities/{activity_id}", data={"sport_type": "WeightTraining"})
    )
    log.info("uploaded %s as %s", t, activity_id)


def upload(dry_run: bool) -> None:
    """Upload pending trainings to Strava as FIT files.

    While fit.py is unchanged, re-uploading a training produces an identical FIT
    file, which Strava rejects as a duplicate. A crash between a successful upload
    and the state write is then recovered on the next run via the duplicate error.
    """
    devices_map = read_json(MILON_DIR / "devices.json")
    uploaded = read_json(UPLOADED_FILE) if UPLOADED_FILE.exists() else {}
    stats = load_stats()
    pending = pending_trainings(stats, uploaded)
    log.info("%d trainings to upload", len(pending))
    if not pending:
        return
    if dry_run:
        FIT_DIR.mkdir(parents=True, exist_ok=True)
        for stat in pending:
            (FIT_DIR / f"{stat['training']['t']}.fit").write_bytes(build_fit(stat))
            print(ACTIVITY_NAME)
            print(build_description(stat, devices_map, stats))
            print()
        return
    headers = {"Authorization": f"Bearer {fresh_token()}"}
    with httpx.Client(base_url=STRAVA_API, headers=headers) as client:
        for stat in pending:
            upload_training(client, stat, devices_map, stats, uploaded)


def garmin_upload(dry_run: bool) -> None:
    """Upload pending trainings to Garmin Connect as FIT files.

    State is written after name and description are set. A crash before that
    is recovered on the next run: Garmin answers 409 and the id is looked up.
    """
    devices_map = read_json(MILON_DIR / "devices.json")
    uploaded = read_json(GARMIN_UPLOADED_FILE) if GARMIN_UPLOADED_FILE.exists() else {}
    stats = load_stats()
    pending = pending_trainings(stats, uploaded)
    log.info("%d trainings to upload", len(pending))
    if not pending:
        return
    FIT_DIR.mkdir(parents=True, exist_ok=True)
    api = None if dry_run else connect()
    for stat in pending:
        t = stat["training"]["t"]
        path = FIT_DIR / f"{t}.fit"
        path.write_bytes(build_fit(stat))
        description = build_description(stat, devices_map, stats)
        if api is None:
            print(ACTIVITY_NAME)
            print(description)
            print()
            continue
        activity_id = upload_fit_file(api, path, training_window(stat)[0])
        api.update_activity(
            activity_id, {"activityName": ACTIVITY_NAME, "description": description}
        )
        uploaded[str(t)] = activity_id
        write_json(GARMIN_UPLOADED_FILE, uploaded)
        log.info("uploaded %s as %s", t, activity_id)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="milon")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export")
    sub.add_parser("strava-auth")
    up = sub.add_parser("upload")
    up.add_argument("--dry-run", action="store_true")
    sub.add_parser("garmin-login")
    gm = sub.add_parser("garmin")
    gm.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    match args.command:
        case "export":
            export()
        case "strava-auth":
            strava_auth()
        case "upload":
            upload(args.dry_run)
        case "garmin-login":
            login()
            log.info("saved garmin tokens")
        case "garmin":
            garmin_upload(args.dry_run)
