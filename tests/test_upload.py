import json

import httpx
import pytest
from conftest import T0, device, training

import milon_export
from milon_export import (
    STRAVA_API,
    upload_training,
    wait_for_upload,
)
from milon_export.describe import ACTIVITY_NAME

DEVICES_MAP = {"537": {"name": "Q LEG PRESS"}}


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch, tmp_path):
    monkeypatch.setattr(milon_export, "POLL_INTERVAL", 0)
    monkeypatch.setattr(milon_export, "UPLOAD_TIMEOUT", 0.05)
    monkeypatch.setattr(milon_export, "UPLOADED_FILE", tmp_path / "uploaded.json")


def strava(handler) -> httpx.Client:
    return httpx.Client(base_url=STRAVA_API, transport=httpx.MockTransport(handler))


def stat():
    return training(T0, [device(537, T0, 100, 130, 8, 60)])


bodies: list[bytes] = []


def make_handler(status: dict, calls: list, put_status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        bodies.append(request.content)
        if request.method == "POST":
            return httpx.Response(201, json={"id": 5, "activity_id": None})
        if request.method == "GET":
            return httpx.Response(200, json=status)
        return httpx.Response(put_status, json={})

    return handler


def run(status, calls, put_status=200):
    uploaded = {}
    with strava(make_handler(status, calls, put_status)) as client:
        upload_training(client, stat(), DEVICES_MAP, [stat()], uploaded)
    return uploaded


def test_success_records_id_and_sets_sport():
    calls = []
    uploaded = run({"activity_id": 9, "error": None}, calls)
    assert uploaded == {str(T0): 9}
    assert calls[-1] == ("PUT", "/api/v3/activities/9")
    assert bodies[-1] == b"sport_type=WeightTraining"
    post = bodies[0]
    for field in (
        b'name="data_type"\r\n\r\nfit',
        b'name="external_id"\r\n\r\nmilon-%d.fit' % T0,
        ACTIVITY_NAME.encode(),
    ):
        assert field in post
    assert json.loads(milon_export.UPLOADED_FILE.read_text()) == {str(T0): 9}


def test_put_failure_keeps_recorded_id():
    with pytest.raises(RuntimeError):
        run({"activity_id": 9, "error": None}, [], put_status=500)
    assert json.loads(milon_export.UPLOADED_FILE.read_text()) == {str(T0): 9}


def test_duplicate_records_existing_id_and_sets_sport():
    calls = []
    error = "duplicate of <a href='http://strava.com/activities/77'>x</a>"
    uploaded = run({"activity_id": None, "error": error}, calls)
    assert uploaded == {str(T0): 77}
    assert calls[-1] == ("PUT", "/api/v3/activities/77")


def test_upload_skips_recorded_trainings(monkeypatch, tmp_path):
    t2 = T0 + 1000
    milon_dir = tmp_path / "milon"
    milon_dir.mkdir()
    (milon_dir / "devices.json").write_text(json.dumps(DEVICES_MAP))
    stats = [stat(), training(t2, [device(537, t2, 100, 130, 8, 60)])]
    (milon_dir / "premium-2611.json").write_text(json.dumps({"stats": stats}))
    milon_export.UPLOADED_FILE.write_text(json.dumps({str(T0): 1}))
    uploaded_ts = []
    monkeypatch.setattr(milon_export, "MILON_DIR", milon_dir)
    monkeypatch.setattr(milon_export, "fresh_token", lambda: "x")
    monkeypatch.setattr(
        milon_export,
        "upload_training",
        lambda client, stat, devices_map, stats, uploaded: uploaded_ts.append(
            stat["training"]["t"]
        ),
    )
    milon_export.upload(dry_run=False)
    assert uploaded_ts == [t2]


def test_other_error_raises():
    with pytest.raises(RuntimeError, match="bad fit"):
        run({"activity_id": None, "error": "bad fit"}, [])
    assert not milon_export.UPLOADED_FILE.exists()


def test_wait_for_upload_times_out():
    with strava(make_handler({"activity_id": None, "error": None}, [])) as client:
        with pytest.raises(TimeoutError):
            wait_for_upload(client, 5)
