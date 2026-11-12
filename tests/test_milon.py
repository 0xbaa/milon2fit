import pytest
from conftest import T0

from milon_export import (
    attendance_months,
    duplicate_activity_id,
    extract_code,
    parse_cookies,
    token_expired,
)

COOKIES = (
    "# Netscape HTTP Cookie File\n\n"
    "#HttpOnly_.www.milonme.com\tTRUE\t/api\tTRUE\t1826031799.451\trs-token\tabc\n"
    "www.milonme.com\tFALSE\t/\tFALSE\t0\tmf\tdef\n"
)

EPOCH_2026_10_31_2330Z = 1793489400


def test_parse_cookies_with_httponly_prefix():
    assert parse_cookies(COOKIES) == {"rs-token": "abc", "mf": "def"}


def test_parse_cookies_wrong_field_count():
    with pytest.raises(ValueError):
        parse_cookies("a\tb\tc\n")


def test_attendance_months_uses_gym_timezone():
    att = [
        {"t": EPOCH_2026_10_31_2330Z, "type": "p"},
        {"t": T0, "type": "p"},
        {"t": T0, "type": "tp"},
    ]
    assert attendance_months(att) == ["2611"]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("x duplicate of <a href='http://strava.com/activities/123'>a</a>", 123),
        ("x duplicate of activity 456", 456),
        ("bad file", None),
    ],
)
def test_duplicate_activity_id(error, expected):
    assert duplicate_activity_id(error) == expected


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
