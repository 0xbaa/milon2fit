from zoneinfo import ZoneInfo

GYM_TZ = ZoneInfo("Europe/Zurich")


def training_window(stat: dict) -> tuple[int, int]:
    """Wall-clock (start, end) epochs covering the training and all its sets."""
    start = min([stat["training"]["t"], *(dev["t"] for dev in stat["devices"])])
    end = max(dev["t"] + dev["d"] for dev in stat["devices"])
    return start, end
