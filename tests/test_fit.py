import pytest
from conftest import T0, device, training
from garmin_fit_sdk import Decoder, Profile, Stream, convert_datetime_to_timestamp

from milon_export.describe import ACTIVITY_NAME
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


def test_records_one_per_distinct_timestamp():
    stat = training(
        T0,
        [
            device(537, T0, 100, 130, 8, 60, d=30),
            device(708, T0 + 30, 30, 40, 8, 60, d=30),
        ],
        d=60,
    )
    records = decode(build_fit(stat))["record_mesgs"]
    assert [r["timestamp"].timestamp() for r in records] == [T0, T0 + 30, T0 + 60]


def test_timer_intervals_sum_to_active_time():
    stat = training(
        T0,
        [
            device(537, T0, 100, 130, 8, 60, d=30),
            device(708, T0 + 100, 30, 40, 8, 60, d=20),
        ],
        d=50,
    )
    events = [
        e for e in decode(build_fit(stat))["event_mesgs"] if e["event"] == "timer"
    ]
    assert [e["event_type"] for e in events] == [
        "start",
        "stop",
        "start",
        "stop_all",
    ]
    stamps = [e["timestamp"].timestamp() for e in events]
    active = (stamps[1] - stamps[0]) + (stamps[3] - stamps[2])
    assert active == stat["training"]["d"]


@pytest.mark.parametrize(("epoch", "offset"), [(T0, 3600), (1782907200, 7200)])
def test_activity_local_timestamp_uses_gym_offset(epoch, offset):
    stat = training(epoch, [device(537, epoch, 100, 130, 8, 60, d=30)])
    activity = decode(build_fit(stat))["activity_mesgs"][0]
    utc_fit = convert_datetime_to_timestamp(activity["timestamp"])
    assert activity["local_timestamp"] - utc_fit == offset


def test_unmapped_station_is_unknown():
    stat = training(T0, [device(999, T0, 6, 8, 10, 90)])
    data = decode(build_fit(stat))
    assert data["set_mesgs"][0]["category"] == "unknown"


@pytest.mark.parametrize(("dev_id", "mapping"), EXERCISES.items())
def test_mapping_exists_in_profile(dev_id, mapping):
    category, name = mapping
    assert category in TYPES["exercise_category"].values()
    assert name in TYPES[f"{category}_exercise_name"].values()


def test_activity_name_in_sport_and_workout_messages():
    stat = training(T0, [device(537, T0, 100, 130, 8, 60, d=30)])
    data = decode(build_fit(stat))
    sport = data["sport_mesgs"][0]
    workout = data["workout_mesgs"][0]
    assert sport["name"] == workout["wkt_name"] == ACTIVITY_NAME
    assert sport["sport"] == workout["sport"] == "training"
    assert sport["sub_sport"] == workout["sub_sport"] == "strength_training"
