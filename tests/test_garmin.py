import subprocess
from datetime import UTC, datetime

import pytest
from conftest import T0, device, training

import milon_export.garmin as garmin
from milon_export.garmin import (
    find_activity_id,
    garmin_password,
    parse_upload_result,
    wait_for_activity,
)
from milon_export.training import pending_trainings


def result(successes=(), failures=()):
    return {
        "detailedImportResult": {
            "uploadId": 1,
            "successes": list(successes),
            "failures": list(failures),
        }
    }


def activity(activity_id, t):
    gmt = datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M:%S")
    return {"activityId": activity_id, "startTimeGMT": gmt}


def test_parse_success():
    payload = result(successes=[{"internalId": 123, "externalId": "x"}])
    assert parse_upload_result(payload) == 123


def test_parse_accepted_but_processing_is_pending():
    assert parse_upload_result(result()) is None


def test_parse_failure_raises_with_message():
    failure = {"messages": [{"code": 500, "content": "Bad file"}]}
    with pytest.raises(RuntimeError, match="Bad file"):
        parse_upload_result(result(failures=[failure]))


def test_find_activity_id_matches_start_time():
    activities = [activity(1, T0 - 86400), activity(2, T0), activity(3, T0 + 5)]
    assert find_activity_id(activities, T0) == 2
    assert find_activity_id(activities, T0 + 3600) is None


class FakeApi:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get_activities_by_date(self, start, end):
        self.calls += 1
        return self.responses.pop(0)


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(garmin, "LOOKUP_INTERVAL", 0)
    monkeypatch.setattr(garmin, "LOOKUP_ATTEMPTS", 3)


def test_wait_for_activity_retries_until_found(fast):
    api = FakeApi([[], [activity(7, T0)]])
    assert wait_for_activity(api, T0) == 7
    assert api.calls == 2


def test_wait_for_activity_raises_when_not_found(fast):
    api = FakeApi([[], [], []])
    with pytest.raises(RuntimeError, match="not found"):
        wait_for_activity(api, T0)


def test_pending_trainings_skips_recorded():
    stats = [training(t, [device(537, t, 1, 1, 1, 1)]) for t in (T0, T0 + 1, T0 + 2)]
    pending = pending_trainings(stats, {str(T0): 5, str(T0 + 2): 6})
    assert [s["training"]["t"] for s in pending] == [T0 + 1]


def test_password_plaintext():
    assert garmin_password({"GARMIN_PASSWORD": "s3cret"}) == "s3cret"


def test_password_command_first_line():
    env = {"GARMIN_PASSWORD_COMMAND": r"printf 'two words\nsecond\n'"}
    assert garmin_password(env) == "two words"


def test_password_command_failure_raises():
    with pytest.raises(subprocess.CalledProcessError):
        garmin_password({"GARMIN_PASSWORD_COMMAND": "false"})


@pytest.mark.parametrize(
    "env",
    [{}, {"GARMIN_PASSWORD": "a", "GARMIN_PASSWORD_COMMAND": "echo b"}],
)
def test_password_needs_exactly_one(env):
    with pytest.raises(RuntimeError, match="GARMIN_PASSWORD.*GARMIN_PASSWORD_COMMAND"):
        garmin_password(env)


@pytest.mark.parametrize(
    ("env", "name"),
    [
        ({"GARMIN_PASSWORD": ""}, "GARMIN_PASSWORD"),
        ({"GARMIN_PASSWORD_COMMAND": "printf ''"}, "GARMIN_PASSWORD_COMMAND"),
        ({"GARMIN_PASSWORD_COMMAND": "printf '\\n'"}, "GARMIN_PASSWORD_COMMAND"),
    ],
)
def test_password_empty_raises(env, name):
    with pytest.raises(RuntimeError, match=f"{name}.*empty"):
        garmin_password(env)
