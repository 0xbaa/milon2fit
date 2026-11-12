import re
from pathlib import Path

import pytest
from conftest import T0, device, training
from garmin_fit_sdk import Decoder, Profile, Stream, convert_datetime_to_timestamp

from milon_export.describe import ACTIVITY_NAME
from milon_export.fit import EXERCISE_RULES, build_fit, exercise_for

TYPES = Profile["types"]
DEVICES_MAP = {
    "537": {"name": "Q LEG PRESS"},
    "708": {"name": "Q LAT PULL V2"},
    "999": {"name": "Unknown Thing"},
}


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
    data = decode(build_fit(stat, DEVICES_MAP))
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
    data = decode(build_fit(stat, DEVICES_MAP))
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
    records = decode(build_fit(stat, DEVICES_MAP))["record_mesgs"]
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
        e
        for e in decode(build_fit(stat, DEVICES_MAP))["event_mesgs"]
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
def test_activity_local_timestamp_uses_gym_offset(epoch, offset):
    stat = training(epoch, [device(537, epoch, 100, 130, 8, 60, d=30)])
    activity = decode(build_fit(stat, DEVICES_MAP))["activity_mesgs"][0]
    utc_fit = convert_datetime_to_timestamp(activity["timestamp"])
    assert activity["local_timestamp"] - utc_fit == offset


def test_unmapped_station_is_unknown():
    stat = training(T0, [device(999, T0, 6, 8, 10, 90)])
    data = decode(build_fit(stat, DEVICES_MAP))
    assert data["set_mesgs"][0]["category"] == "unknown"


@pytest.mark.parametrize(("keywords", "category", "name"), EXERCISE_RULES)
def test_rules_exist_in_profile(keywords, category, name):
    assert keywords == tuple(k.upper() for k in keywords)
    assert category in TYPES["exercise_category"].values()
    if name is not None:
        assert name in TYPES[f"{category}_exercise_name"].values()


def exercise_name(category: str, subtype: int | None) -> str | None:
    return None if subtype is None else TYPES[f"{category}_exercise_name"][subtype]


@pytest.mark.parametrize(
    ("machine", "category", "name"),
    [
        ("Q ROTATOR KOMBI", "core", "russian_twist"),
        ("Basic Torso Twist left", "core", "russian_twist"),
        ("Q BUTTERFLY REV", "flye", "incline_reverse_flye"),
        ("Basic Butterfly Revers-B", "flye", "incline_reverse_flye"),
        ("BUTTERFLY REVERSE MED", "flye", "incline_reverse_flye"),
        ("Basic cabletec butterfly 1", "flye", "cable_crossover"),
        ("Basic cabletec cross 3", "flye", "cable_crossover"),
        ("Q BUTTERFLY", "flye", None),
        ("MILCANIC BRUSTMASCHINE", "flye", None),
        ("Q CHEST PRESS", "bench_press", None),
        ("MILCANIC BANKDRÜCKER A", "bench_press", None),
        ("Basic Bank drücken-B", "bench_press", None),
        ("Q LAT PULL V2", "pull_up", "lat_pulldown"),
        ("Basic Latzug-B", "pull_up", "lat_pulldown"),
        ("MILCANIC BACK PULLDOWN", "pull_up", "lat_pulldown"),
        ("Basic cabletec lat 2", "pull_up", "lat_pulldown"),
        ("Basic cabletec universal lat 2", "pull_up", "lat_pulldown"),
        ("MILCANIC LATERAL RAISE", "lateral_raise", "seated_lateral_raise"),
        ("Basic cabletec low pull 1", "row", "seated_cable_row"),
        ("Q SEATED ROW", "row", "seated_cable_row"),
        ("Basic Rudermaschine-C", "row", "seated_cable_row"),
        ("Q SHOULDER PRESS V2", "shoulder_press", None),
        ("MILCANIC SCHULTERDRÜCK A", "shoulder_press", None),
        ("Q LEG PRESS", "squat", "leg_press"),
        ("BEINPRESSE VARIO MED", "squat", "leg_press"),
        ("Q LEG EXTENSION", "squat", None),
        ("BEINSTRECKER MED", "squat", None),
        ("Q LEG CURL", "leg_curl", "weighted_leg_curl"),
        ("BEINBEUGER PP MED", "leg_curl", "weighted_leg_curl"),
        ("Q ABDUCTOR", "hip_stability", "weighted_standing_hip_abduction"),
        ("Basic Abduktoren-B", "hip_stability", "weighted_standing_hip_abduction"),
        ("Q ADDUCTOR", "hip_stability", "weighted_standing_adduction"),
        ("Q ABDOMINAL CRUNCH", "crunch", "weighted_crunch"),
        ("BAUCHBEUGER B MED", "crunch", "weighted_crunch"),
        ("Q BACK EXTENSION", "hyperextension", "weighted_spine_extension"),
        ("Basic Unterer Rücken-B", "hyperextension", "weighted_spine_extension"),
        ("RÜCKENSTRECKER B MED", "hyperextension", "weighted_spine_extension"),
        ("Q HIP THRUST", "hip_raise", "barbell_hip_thrust_with_bench"),
        (
            "Basic Glutaeus stehend-B",
            "hip_stability",
            "weighted_quadruped_hip_extension",
        ),
        ("Basic Wadenmaschine-C", "calf_raise", None),
        ("Basic Beinheben stehend-B", "leg_raise", None),
        ("Basic Leg lifting standing", "leg_raise", None),
        ("Q DIPS", "triceps_extension", "weighted_dip"),
        ("Q TRICEPS", "triceps_extension", None),
        ("TRIZEPS MED", "triceps_extension", None),
        ("Q BICEPS", "curl", None),
        ("MILCANIC ARM CURL", "curl", None),
        ("Basic cabletec universal 1", "unknown", None),
        ("MILBRATION PLATE A", "unknown", None),
        ("未知裝置", "unknown", None),
    ],
)
def test_exercise_for(machine, category, name):
    cat, subtype = exercise_for(machine)
    assert (cat, exercise_name(cat, subtype)) == (category, name)


def is_expected_unknown(machine: str) -> bool:
    return (
        "MILBRATION" in machine.upper()
        or re.fullmatch(r"basic cabletec universal \d", machine, re.IGNORECASE)
        is not None
        or machine == "未知裝置"
    )


FIXTURE = Path(__file__).parent / "fixtures" / "milon_machines.txt"


@pytest.mark.parametrize("machine", FIXTURE.read_text().splitlines())
def test_all_milon_machines_mapped_except_known_unknowns(machine):
    category, _ = exercise_for(machine)
    assert (category == "unknown") == is_expected_unknown(machine)


def test_set_uses_station_name_for_exercise():
    stat = training(T0, [device(537, T0, 100, 130, 8, 60)])
    devices_map = {"537": {"name": "Q LEG PRESS"}}
    sets = decode(build_fit(stat, devices_map))["set_mesgs"]
    assert sets[0]["category"] == "squat"
    assert TYPES["squat_exercise_name"][sets[0]["category_subtype"]] == "leg_press"


def test_category_only_station_has_no_subtype():
    stat = training(T0, [device(532, T0, 46, 60, 10, 99)])
    sets = decode(build_fit(stat, {"532": {"name": "Q CHEST PRESS"}}))["set_mesgs"]
    assert sets[0]["category"] == "bench_press"
    assert "category_subtype" not in sets[0]


def test_activity_name_in_sport_and_workout_messages():
    stat = training(T0, [device(537, T0, 100, 130, 8, 60, d=30)])
    data = decode(build_fit(stat, DEVICES_MAP))
    sport = data["sport_mesgs"][0]
    workout = data["workout_mesgs"][0]
    assert sport["name"] == workout["wkt_name"] == ACTIVITY_NAME
    assert sport["sport"] == workout["sport"] == "training"
    assert sport["sub_sport"] == workout["sub_sport"] == "strength_training"
