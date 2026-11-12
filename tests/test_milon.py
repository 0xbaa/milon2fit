from datetime import datetime

from milon_export import (
    attendance_months,
    build_payload,
    extract_code,
    parse_cookies,
    token_expired,
)

COOKIES = (
    "# Netscape HTTP Cookie File\n\n"
    ".www.milonme.com\tTRUE\t/api\tTRUE\t1826031799.451\trs-token\tabc\n"
    "www.milonme.com\tFALSE\t/\tFALSE\t0\tmf\tdef\n"
)


def test_parse_cookies():
    assert parse_cookies(COOKIES) == {"rs-token": "abc", "mf": "def"}


def test_attendance_months_skips_non_premium():
    t1 = datetime(2026, 11, 3, 12).timestamp()
    t2 = datetime(2026, 11, 20, 12).timestamp()
    t3 = datetime(2026, 10, 31, 23, 30).timestamp()
    att = [
        {"t": t1, "type": "p"},
        {"t": t2, "type": "p"},
        {"t": t3, "type": "p"},
        {"t": t1, "type": "tp"},
    ]
    assert attendance_months(att) == ["2610", "2611"]


def test_build_payload():
    t = datetime(2026, 11, 3, 18, 30, 5).timestamp()
    stat = {
        "training": {"t": t, "d": 1800, "ws": 250, "moves": 120, "plan_name": "Plan A"},
        "devices": [
            {
                "id": 2,
                "t": t + 300,
                "d": 60,
                "aw": 30,
                "adw": 25,
                "ws": 10,
                "moves": 12,
                "tr_q": 90,
            },
            {
                "id": 1,
                "t": t,
                "d": 60,
                "aw": 40,
                "adw": 35,
                "ws": 12,
                "moves": 10,
                "tr_q": 80,
            },
        ],
    }
    devices = {"1": {"name": "LEG PRESS"}, "2": {"name": "CHEST"}}
    payload = build_payload(stat, devices)
    assert payload["start_date_local"] == "2026-11-03T18:30:05"
    assert payload["elapsed_time"] == 1800
    assert payload["name"] == "milon circle Plan A"
    lines = payload["description"].splitlines()
    assert lines[0] == "250 kcal, 120 moves, 30 min"
    assert lines[2].startswith("LEG PRESS: 40/35 kg")
    assert lines[3].startswith("CHEST")


def test_token_expired():
    assert token_expired({"expires_at": 100}, now=100)
    assert not token_expired({"expires_at": 1000}, now=100)


def test_extract_code():
    assert extract_code("http://localhost/?state=&code=xyz&scope=a") == "xyz"
    assert extract_code(" xyz\n") == "xyz"
