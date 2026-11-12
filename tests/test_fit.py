import pytest
from conftest import T0, device, training
from garmin_fit_sdk import Decoder, Profile, Stream, convert_datetime_to_timestamp

from milon_export.fit import EXERCISES, build_fit

TYPES = Profile["types"]


def decode(data: bytes) -> dict:
    messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    assert errors == []
    return messages


def test_build_fit_roundtrip():
    stat = training(
        T0,
        [
            device(708, T0 + 100, 30, 40, 10, 90),
            device(537, T0, 100, 130, 8, 60, ws=20),
        ],
        ws=250,
        d=120,
    )
    data = decode(build_fit(stat))
    session = data["session_mesgs"][0]
    assert session["total_calories"] == 250
    assert session["total_elapsed_time"] == 160
    assert session["total_timer_time"] == 120
    assert session["sub_sport"] == "strength_training"
    assert data["file_id_mesgs"][0]["type"] == "activity"
    assert [lap["total_calories"] for lap in data["lap_mesgs"]] == [20, 10]
    sets = data["set_mesgs"]
    assert [s["repetitions"] for s in sets] == [8, 10]
    assert sets[0]["weight"] == 100
    assert sets[0]["start_time"].timestamp() == T0
    assert sets[0]["category"] == "squat"
    assert TYPES["squat_exercise_name"][sets[0]["category_subtype"]] == "leg_press"
    assert sets[1]["category"] == "pull_up"


def test_session_spans_all_sets():
    stat = training(
        T0,
        [device(537, T0 - 1, 100, 130, 8, 60), device(708, T0 + 500, 30, 40, 10, 90)],
        d=100,
    )
    data = decode(build_fit(stat))
    session = data["session_mesgs"][0]
    assert session["start_time"].timestamp() == T0 - 1
    assert session["total_elapsed_time"] == 561
    assert session["total_timer_time"] == 100
    assert session["timestamp"].timestamp() == T0 + 560
    for lap in data["lap_mesgs"]:
        assert lap["start_time"] >= session["start_time"]
        assert lap["timestamp"] <= session["timestamp"]
    stops = [e for e in data["event_mesgs"] if e["event_type"] == "stop_all"]
    assert stops[0]["timestamp"] == session["timestamp"]
    assert data["activity_mesgs"][0]["timestamp"] == session["timestamp"]


def test_records_at_session_start_and_set_boundaries():
    stat = training(T0, [device(537, T0, 100, 130, 8, 60, d=30)])
    records = decode(build_fit(stat))["record_mesgs"]
    assert [r["timestamp"].timestamp() for r in records] == [T0, T0, T0 + 30]


def test_activity_local_timestamp_uses_gym_offset():
    stat = training(T0, [device(537, T0, 100, 130, 8, 60, d=30)])
    activity = decode(build_fit(stat))["activity_mesgs"][0]
    utc_fit = convert_datetime_to_timestamp(activity["timestamp"])
    assert activity["local_timestamp"] - utc_fit == 3600


def test_unmapped_station_is_unknown():
    stat = training(T0, [device(999, T0, 6, 8, 10, 90)])
    data = decode(build_fit(stat))
    assert data["set_mesgs"][0]["category"] == "unknown"


@pytest.mark.parametrize(("dev_id", "mapping"), EXERCISES.items())
def test_mapping_exists_in_profile(dev_id, mapping):
    category, name = mapping
    assert category in TYPES["exercise_category"].values()
    assert name in TYPES[f"{category}_exercise_name"].values()
