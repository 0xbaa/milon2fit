from pathlib import Path

import pytest
from conftest import T0, device, training
from garmin_fit_sdk import Decoder, Profile, Stream, convert_datetime_to_timestamp

from milon_export.describe import ACTIVITY_NAME
from milon_export.fit import EXERCISE_RULES, build_fit, exercise_for

TYPES = Profile["types"]


def decode(data: bytes) -> dict:
    messages, errors = Decoder(Stream.from_byte_array(bytearray(data))).read()
    assert errors == []
    return messages


def test_build_fit_roundtrip(devices_map):
    stat = training(
        T0,
        [
            device(708, T0 + 100, 30, 40, 10, 90),
            device(537, T0, 100, 130, 8, 60, ws=20),
        ],
        ws=250,
        d=120,
    )
    data = decode(build_fit(stat, devices_map))
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


def test_session_spans_all_sets(devices_map):
    stat = training(
        T0,
        [device(537, T0 - 1, 100, 130, 8, 60), device(708, T0 + 500, 30, 40, 10, 90)],
        d=100,
    )
    data = decode(build_fit(stat, devices_map))
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


def test_records_one_per_distinct_timestamp(devices_map):
    stat = training(
        T0,
        [
            device(537, T0, 100, 130, 8, 60, d=30),
            device(708, T0 + 30, 30, 40, 8, 60, d=30),
        ],
        d=60,
    )
    records = decode(build_fit(stat, devices_map))["record_mesgs"]
    assert [r["timestamp"].timestamp() for r in records] == [T0, T0 + 30, T0 + 60]


def test_timer_intervals_sum_to_active_time(devices_map):
    stat = training(
        T0,
        [
            device(537, T0, 100, 130, 8, 60, d=30),
            device(708, T0 + 100, 30, 40, 8, 60, d=20),
        ],
        d=50,
    )
    events = [
        e
        for e in decode(build_fit(stat, devices_map))["event_mesgs"]
        if e["event"] == "timer"
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
def test_activity_local_timestamp_uses_gym_offset(epoch, offset, devices_map):
    stat = training(epoch, [device(537, epoch, 100, 130, 8, 60, d=30)])
    activity = decode(build_fit(stat, devices_map))["activity_mesgs"][0]
    utc_fit = convert_datetime_to_timestamp(activity["timestamp"])
    assert activity["local_timestamp"] - utc_fit == offset


def test_unmapped_station_is_unknown(devices_map):
    stat = training(T0, [device(999, T0, 6, 8, 10, 90)])
    data = decode(build_fit(stat, devices_map))
    assert data["set_mesgs"][0]["category"] == "unknown"


def test_rule_keywords_are_uppercase():
    for keywords, _, _ in EXERCISE_RULES:
        assert keywords == tuple(k.upper() for k in keywords)


def exercise_name(category: str, subtype: int | None) -> str:
    return "" if subtype is None else TYPES[f"{category}_exercise_name"][subtype]


def test_mapping_of_all_milon_machines():
    expected = {}
    for line in FIXTURE.read_text().splitlines():
        machine, category, name = line.split("\t")
        expected[machine] = (category, name)
    actual = {}
    for machine in expected:
        category, subtype = exercise_for(machine)
        actual[machine] = (category, exercise_name(category, subtype))
    assert actual == expected


FIXTURE = Path(__file__).parent / "fixtures" / "milon_machines.tsv"


def test_exercise_follows_machine_name_not_device_id():
    stat = training(T0, [device(532, T0, 100, 130, 8, 60)])
    sets = decode(build_fit(stat, {"532": {"name": "Q LEG PRESS"}}))["set_mesgs"]
    assert sets[0]["category"] == "squat"
    assert TYPES["squat_exercise_name"][sets[0]["category_subtype"]] == "leg_press"


def test_category_only_station_has_no_subtype():
    stat = training(T0, [device(532, T0, 46, 60, 10, 99)])
    sets = decode(build_fit(stat, {"532": {"name": "Q CHEST PRESS"}}))["set_mesgs"]
    assert sets[0]["category"] == "bench_press"
    assert "category_subtype" not in sets[0]


def test_activity_name_in_sport_and_workout_messages(devices_map):
    stat = training(T0, [device(537, T0, 100, 130, 8, 60, d=30)])
    data = decode(build_fit(stat, devices_map))
    sport = data["sport_mesgs"][0]
    workout = data["workout_mesgs"][0]
    assert sport["name"] == workout["wkt_name"] == ACTIVITY_NAME
    assert sport["sport"] == workout["sport"] == "training"
    assert sport["sub_sport"] == workout["sub_sport"] == "strength_training"
