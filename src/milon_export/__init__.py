import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

log = logging.getLogger("milon")

API = "https://www.milonme.com/api/"
COOKIE_FILE = Path("cookies-milonme-com.txt")
MILON_DIR = Path("data/milon")
TOKEN_FILE = Path("data/strava-token.json")
UPLOADED_FILE = Path("data/strava-uploaded.json")
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/activities"
TOKEN_EXPIRY_MARGIN = 60


def parse_cookies(text: str) -> dict[str, str]:
    """Netscape cookie file to name/value map (MozillaCookieJar drops `mf`)."""
    cookies = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) != 7:
            raise ValueError(f"expected 7 tab-separated fields, got {len(fields)}")
        cookies[fields[5]] = fields[6]
    return cookies


def attendance_months(attendance: list[dict]) -> list[str]:
    """Distinct YYMM (local time) of premium ("p") attendance entries, sorted."""
    months = set()
    for entry in attendance:
        if entry["type"] != "p":
            log.warning("skipping attendance type %s", entry["type"])
            continue
        months.add(datetime.fromtimestamp(entry["t"]).strftime("%y%m"))
    return sorted(months)


def build_payload(stat: dict, devices: dict) -> dict:
    training = stat["training"]
    plan = training["plan_name"]
    name = f"milon circle {plan}" if plan else "milon circle"
    lines = [
        f"{training['ws']} kcal, {training['moves']} moves, {training['d'] // 60} min",
        "",
    ]
    for dev in sorted(stat["devices"], key=lambda d: d["t"]):
        lines.append(
            f"{devices[str(dev['id'])]['name']}: {dev['aw']}/{dev['adw']} kg, "
            f"{dev['moves']} moves, {dev['ws']} kcal, {dev['tr_q']}%"
        )
    return {
        "name": name,
        "sport_type": "WeightTraining",
        "start_date_local": datetime.fromtimestamp(training["t"]).isoformat(
            timespec="seconds"
        ),
        "elapsed_time": training["d"],
        "trainer": 1,
        "description": "\n".join(lines),
    }


def token_expired(token: dict, now: float | None = None) -> bool:
    now = time.time() if now is None else now
    return token["expires_at"] <= now + TOKEN_EXPIRY_MARGIN


def extract_code(pasted: str) -> str:
    pasted = pasted.strip()
    if "code=" not in pasted:
        return pasted
    return parse_qs(urlparse(pasted).query)["code"][0]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_json(path: Path):
    return json.loads(path.read_text())


def milon_get(client: httpx.Client, path: str):
    resp = client.get(path)
    resp.raise_for_status()
    return resp.json()


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
        scope="activity:write,activity:read_all",
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
    resp.raise_for_status()
    write_json(TOKEN_FILE, resp.json())
    log.info("saved %s", TOKEN_FILE)


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
        resp.raise_for_status()
        token = resp.json()
        write_json(TOKEN_FILE, token)
        log.info("refreshed strava token")
    return token["access_token"]


def load_stats() -> list[dict]:
    stats = []
    for path in sorted(MILON_DIR.glob("premium-*.json")):
        stats.extend(read_json(path)["stats"])
    return sorted(stats, key=lambda s: s["training"]["t"])


def upload(dry_run: bool) -> None:
    devices = read_json(MILON_DIR / "devices.json")
    uploaded = read_json(UPLOADED_FILE) if UPLOADED_FILE.exists() else {}
    pending = [s for s in load_stats() if str(s["training"]["t"]) not in uploaded]
    log.info("%d trainings to upload", len(pending))
    if dry_run:
        for stat in pending:
            print(json.dumps(build_payload(stat, devices), indent=2))
        return
    headers = {"Authorization": f"Bearer {fresh_token()}"}
    for stat in pending:
        resp = httpx.post(
            STRAVA_ACTIVITIES_URL, headers=headers, data=build_payload(stat, devices)
        )
        resp.raise_for_status()
        uploaded[str(stat["training"]["t"])] = resp.json()["id"]
        write_json(UPLOADED_FILE, uploaded)
        log.info("uploaded %s as %s", stat["training"]["t"], resp.json()["id"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="milon")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("export")
    sub.add_parser("strava-auth")
    up = sub.add_parser("upload")
    up.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    match args.command:
        case "export":
            export()
        case "strava-auth":
            strava_auth()
        case "upload":
            upload(args.dry_run)
