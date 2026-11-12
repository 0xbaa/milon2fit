import pytest
from conftest import T0, device, training

from milon_export.garmin import UploadOutcome, parse_upload_result
from milon_export.training import pending_trainings


def result(successes=(), failures=()):
    return {
        "detailedImportResult": {
            "uploadId": 1,
            "successes": list(successes),
            "failures": list(failures),
        }
    }


def failure(code, content, **extra):
    return {"messages": [{"code": code, "content": content}], **extra}


def test_parse_success():
    payload = result(successes=[{"internalId": 123, "externalId": "x"}])
    assert parse_upload_result(payload) == UploadOutcome(123, duplicate=False)


def test_parse_duplicate_with_id():
    payload = result(failures=[failure(202, "Duplicate Activity", internalId=456)])
    assert parse_upload_result(payload) == UploadOutcome(456, duplicate=True)


def test_parse_duplicate_without_id():
    payload = result(failures=[failure(202, "Duplicate Activity")])
    assert parse_upload_result(payload) == UploadOutcome(None, duplicate=True)


def test_parse_other_failure_raises_with_message():
    payload = result(failures=[failure(500, "Bad file")])
    with pytest.raises(RuntimeError, match="Bad file"):
        parse_upload_result(payload)


def test_parse_empty_result_raises():
    with pytest.raises(RuntimeError):
        parse_upload_result(result())


def test_pending_trainings_skips_recorded_including_null():
    stats = [training(t, [device(537, t, 1, 1, 1, 1)]) for t in (T0, T0 + 1, T0 + 2)]
    pending = pending_trainings(stats, {str(T0): 5, str(T0 + 2): None})
    assert [s["training"]["t"] for s in pending] == [T0 + 1]
