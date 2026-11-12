import pytest

from milon_export import (
    attendance_months,
    build_payload,
    extract_code,
    parse_cookies,
    token_expired,
)

COOKIES = (
    "# Netscape HTTP Cookie File\n\n"
    "#HttpOnly_.www.milonme.com\tTRUE\t/api\tTRUE\t1826031799.451\trs-token\tabc\n"
    "www.milonme.com\tFALSE\t/\tFALSE\t0\tmf\tdef\n"
)

EPOCH_2026_11_10 = 1794298668
EPOCH_2026_10_31_2330Z = 1793489400


def test_parse_cookies_with_httponly_prefix():
    assert parse_cookies(COOKIES) == {"rs-token": "abc", "mf": "def"}


def test_parse_cookies_wrong_field_count():
    with pytest.raises(ValueError):
        parse_cookies("a\tb\tc\n")


def test_attendance_months_uses_gym_timezone():
    att = [
        {"t": EPOCH_2026_10_31_2330Z, "type": "p"},
        {"t": EPOCH_2026_11_10, "type": "p"},
        {"t": EPOCH_2026_11_10, "type": "tp"},
    ]
    assert attendance_months(att) == ["2611"]


def test_build_payload():
    t = EPOCH_2026_11_10
    stat = {
        "training": {"t": t, "d": 1800, "ws": 250, "moves": 120, "plan_name": "Plan A"},
        "devices": [
            {
                "id": 2,
                "t": t + 300,
                "aw": 30,
                "adw": 25,
                "ws": 10,
                "moves": 12,
                "tr_q": 90,
            },
            {"id": 1, "t": t, "aw": 40, "adw": 35, "ws": 12, "moves": 10, "tr_q": 80},
        ],
    }
    devices = {"1": {"name": "LEG PRESS"}, "2": {"name": "CHEST"}}
    payload = build_payload(stat, devices)
    assert payload["start_date_local"] == "2026-11-10T09:17:48"
    assert payload["elapsed_time"] == 1800
    assert payload["name"] == "milon circle Plan A"
    lines = payload["description"].splitlines()
    assert lines[0] == "250 kcal, 120 moves, 30 min"
    assert lines[2].startswith("LEG PRESS: 40/35 kg")
    assert lines[3].startswith("CHEST")


def test_token_expired():
    assert token_expired({"expires_at": 100}, now=100)
    assert token_expired({"expires_at": 159}, now=100)
    assert not token_expired({"expires_at": 1000}, now=100)


def test_extract_code():
    url = "http://localhost/?state=&code=xyz&scope=read,activity:write"
    assert extract_code(url) == "xyz"
    assert extract_code(" xyz\n") == "xyz"


def test_extract_code_denied():
    with pytest.raises(ValueError):
        extract_code("http://localhost/?error=access_denied")


def test_extract_code_missing_scope():
    with pytest.raises(ValueError):
        extract_code("http://localhost/?code=xyz&scope=read")
