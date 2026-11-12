import pytest
from conftest import T0, device, training
from garmin_fit_sdk import Decoder, Profile, Stream

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
    )
    data = decode(build_fit(stat))
    session = data["session_mesgs"][0]
    assert session["total_calories"] == 250
    assert session["total_elapsed_time"] == 1800
    assert session["sub_sport"] == "strength_training"
    assert data["file_id_mesgs"][0]["type"] == "activity"
    assert [lap["total_calories"] for lap in data["lap_mesgs"]] == [20, 10]
    sets = data["set_mesgs"]
    assert [s["repetitions"] for s in sets] == [8, 10]
    assert sets[0]["weight"] == 100
    assert sets[0]["start_time"].timestamp() == T0
    assert sets[0]["category"] == "squat"
    assert sets[1]["category"] == "pull_up"


def test_unmapped_station_is_unknown():
    stat = training(T0, [device(999, T0, 6, 8, 10, 90)])
    data = decode(build_fit(stat))
    assert data["set_mesgs"][0]["category"] == "unknown"


@pytest.mark.parametrize(("dev_id", "mapping"), EXERCISES.items())
def test_mapping_exists_in_profile(dev_id, mapping):
    category, name = mapping
    assert category in TYPES["exercise_category"].values()
    assert name in TYPES[f"{category}_exercise_name"].values()


def test_exercise_subtype_roundtrip():
    stat = training(T0, [device(537, T0, 100, 130, 8, 60)])
    data = decode(build_fit(stat))
    subtype = data["set_mesgs"][0]["category_subtype"]
    assert TYPES["squat_exercise_name"][subtype] == "leg_press"
