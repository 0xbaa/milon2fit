import json
from datetime import UTC, datetime
from pathlib import Path

from garmin_fit_sdk import Encoder, Profile

from milon_export.describe import ACTIVITY_NAME
from milon_export.training import GYM_TZ, training_window

MESG = Profile["mesg_num"]
TYPES = Profile["types"]

# Each rule: keywords matched against the upper-cased milon machine name; the first
# rule with any keyword as a substring wins, so file order matters. "name": null means
# FIT has no matching exercise and the category alone avoids a wrong name.
RULES_FILE = Path(__file__).with_name("exercise_rules.json")
EXERCISE_RULES: list[tuple[tuple[str, ...], str, str | None]] = [
    (tuple(rule["keywords"]), rule["category"], rule["name"])
    for rule in json.loads(RULES_FILE.read_text())
]

# Resolved at import time so a misspelled category or name fails immediately.
RESOLVED_RULES: list[tuple[tuple[str, ...], str, int | None]] = [
    (
        keywords,
        category,
        None
        if name is None
        else {v: k for k, v in TYPES[f"{category}_exercise_name"].items()}[name],
    )
    for keywords, category, name in EXERCISE_RULES
]


def exercise_for(machine: str) -> tuple[str, int | None]:
    """FIT category and exercise-name number for a milon machine name."""
    upper = machine.upper()
    for keywords, category, number in RESOLVED_RULES:
        if any(keyword in upper for keyword in keywords):
            return category, number
    return "unknown", None


def utc(t: int) -> datetime:
    return datetime.fromtimestamp(t, UTC)


def set_mesg(index: int, dev: dict, machine: str) -> dict:
    category, subtype = exercise_for(machine)
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


def timer_mesg(t: int, event_type: str) -> dict:
    return {
        "mesg_num": MESG["EVENT"],
        "timestamp": utc(t),
        "event": "timer",
        "event_type": event_type,
    }


def build_fit(stat: dict, devices_map: dict) -> bytes:
    """Encode a training as a FIT activity.

    The timer runs only during sets, so start->stop intervals sum to
    training["d"] (the summed active set time).
    """
    training = stat["training"]
    start_t, end_t = training_window(stat)
    start, end = utc(start_t), utc(end_t)
    local_end = end + end.astimezone(GYM_TZ).utcoffset()
    devs = sorted(stat["devices"], key=lambda dev: dev["t"])
    pending = sorted(
        {start_t, *(dev["t"] for dev in devs), *(dev["t"] + dev["d"] for dev in devs)}
    )
    encoder = Encoder()

    def write_records(upto: int) -> None:
        while pending and pending[0] <= upto:
            encoder.write_mesg(record_mesg(pending.pop(0)))

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
            "mesg_num": MESG["SPORT"],
            "sport": "training",
            "sub_sport": "strength_training",
            "name": ACTIVITY_NAME,
        }
    )
    encoder.write_mesg(
        {
            "mesg_num": MESG["WORKOUT"],
            "sport": "training",
            "sub_sport": "strength_training",
            "wkt_name": ACTIVITY_NAME,
        }
    )
    for index, dev in enumerate(devs):
        write_records(dev["t"])
        encoder.write_mesg(timer_mesg(dev["t"], "start"))
        write_records(dev["t"] + dev["d"])
        encoder.write_mesg(set_mesg(index, dev, devices_map[str(dev["id"])]["name"]))
        encoder.write_mesg(lap_mesg(index, dev))
        last = index == len(devs) - 1
        encoder.write_mesg(
            timer_mesg(dev["t"] + dev["d"], "stop_all" if last else "stop")
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
