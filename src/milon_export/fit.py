from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from garmin_fit_sdk import Encoder, Profile

from milon_export.describe import training_window

MESG = Profile["mesg_num"]
TYPES = Profile["types"]
GYM_TZ = ZoneInfo("Europe/Zurich")

# milon device type id -> (FIT exercise_category, FIT <category>_exercise_name)
EXERCISES: dict[int, tuple[str, str]] = {
    531: ("hyperextension", "weighted_spine_extension"),
    532: ("bench_press", "barbell_bench_press"),
    533: ("row", "seated_cable_row"),
    534: ("crunch", "weighted_crunch"),
    536: ("leg_curl", "weighted_leg_curl"),
    537: ("squat", "leg_press"),
    542: ("hip_stability", "weighted_standing_adduction"),
    543: ("hip_stability", "weighted_standing_hip_abduction"),
    545: ("flye", "incline_reverse_flye"),
    546: ("shoulder_stability", "cable_external_rotation"),
    708: ("pull_up", "lat_pulldown"),
    709: ("shoulder_press", "seated_dumbbell_shoulder_press"),
}


EXERCISE_IDS: dict[int, tuple[str, int]] = {
    dev_id: (
        category,
        {v: k for k, v in TYPES[f"{category}_exercise_name"].items()}[name],
    )
    for dev_id, (category, name) in EXERCISES.items()
}


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, UTC)


def set_mesg(index: int, dev: dict) -> dict:
    category, subtype = EXERCISE_IDS.get(dev["id"], ("unknown", None))
    mesg = {
        "mesg_num": MESG["SET"],
        "timestamp": utc(dev["t"] + dev["d"]),
        "start_time": utc(dev["t"]),
        "duration": dev["d"],
        "repetitions": dev["moves"],
        "weight": dev["aw"],
        "set_type": "active",
        "category": [category],
        "message_index": index,
    }
    if subtype is not None:
        mesg["category_subtype"] = [subtype]
    return mesg


def lap_mesg(index: int, dev: dict) -> dict:
    return {
        "mesg_num": MESG["LAP"],
        "message_index": index,
        "timestamp": utc(dev["t"] + dev["d"]),
        "start_time": utc(dev["t"]),
        "total_elapsed_time": dev["d"],
        "total_timer_time": dev["d"],
        "total_calories": dev["ws"],
        "sport": "training",
        "sub_sport": "strength_training",
    }


def record_mesg(t: int) -> dict:
    return {"mesg_num": MESG["RECORD"], "timestamp": utc(t)}


def build_fit(stat: dict) -> bytes:
    training = stat["training"]
    start_t, end_t = training_window(stat)
    start, end = utc(start_t), utc(end_t)
    local_end = end + end.astimezone(GYM_TZ).utcoffset()
    devs = sorted(stat["devices"], key=lambda d: d["t"])
    encoder = Encoder()
    encoder.write_mesg(
        {
            "mesg_num": MESG["FILE_ID"],
            "type": "activity",
            "manufacturer": "development",
            "product": 0,
            "time_created": start,
        }
    )
    encoder.write_mesg(
        {
            "mesg_num": MESG["EVENT"],
            "timestamp": start,
            "event": "timer",
            "event_type": "start",
        }
    )
    encoder.write_mesg(record_mesg(start_t))
    for index, dev in enumerate(devs):
        encoder.write_mesg(record_mesg(dev["t"]))
        encoder.write_mesg(record_mesg(dev["t"] + dev["d"]))
        encoder.write_mesg(set_mesg(index, dev))
        encoder.write_mesg(lap_mesg(index, dev))
    encoder.write_mesg(
        {
            "mesg_num": MESG["EVENT"],
            "timestamp": end,
            "event": "timer",
            "event_type": "stop_all",
        }
    )
    encoder.write_mesg(
        {
            "mesg_num": MESG["SESSION"],
            "message_index": 0,
            "timestamp": end,
            "start_time": start,
            "total_elapsed_time": end_t - start_t,
            "total_timer_time": training["d"],
            "total_calories": training["ws"],
            "sport": "training",
            "sub_sport": "strength_training",
            "first_lap_index": 0,
            "num_laps": len(devs),
        }
    )
    encoder.write_mesg(
        {
            "mesg_num": MESG["ACTIVITY"],
            "timestamp": end,
            "local_timestamp": local_end,
            "total_timer_time": training["d"],
            "num_sessions": 1,
            "type": "manual",
            "event": "activity",
            "event_type": "stop",
        }
    )
    return encoder.close()
