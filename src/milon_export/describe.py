UP, DOWN = "↑", "↓"


def station_name(raw: str) -> str:
    return raw.removeprefix("Q ").removesuffix(" V2").title()


def build_name(training: dict) -> str:
    plan = training["plan_name"]
    return f"milon circle {plan}" if plan else "milon circle"


def station_rounds(devices: list[dict]) -> dict[int, list[dict]]:
    """Device entries grouped by station id, in first-appearance order."""
    rounds: dict[int, list[dict]] = {}
    for dev in sorted(devices, key=lambda d: d["t"]):
        rounds.setdefault(dev["id"], []).append(dev)
    return rounds


def training_window(stat: dict) -> tuple[int, int]:
    """Wall-clock (start, end) epochs covering the training and all its sets."""
    start = min([stat["training"]["t"], *(dev["t"] for dev in stat["devices"])])
    end = max(dev["t"] + dev["d"] for dev in stat["devices"])
    return start, end


def previous_max_aw(stats: list[dict], t: int, dev_id: int) -> int | None:
    """Max aw of the latest training before `t` that includes the station.

    `stats` must be sorted ascending by training start.
    """
    for stat in reversed(stats):
        if stat["training"]["t"] >= t:
            continue
        aws = [dev["aw"] for dev in stat["devices"] if dev["id"] == dev_id]
        if aws:
            return max(aws)
    return None


def trend(current: int, previous: int | None) -> str:
    if previous is None or current == previous:
        return ""
    return f" {UP}" if current > previous else f" {DOWN}"


def build_description(stat: dict, devices_map: dict, stats: list[dict]) -> str:
    training = stat["training"]
    start, end = training_window(stat)
    volume = sum(dev["aw"] * dev["moves"] for dev in stat["devices"]) / 1000
    lines = [
        f"{training['ws']} kcal · {training['moves']} reps · "
        f"{training['d'] // 60} min active · {(end - start) // 60} min total · "
        f"{volume:.1f} t moved",
        "",
    ]
    for dev_id, rounds in station_rounds(stat["devices"]).items():
        best = max(rounds, key=lambda r: r["aw"])
        reps = "+".join(str(r["moves"]) for r in rounds)
        quality = "/".join(str(r["tr_q"]) for r in rounds)
        arrow = trend(best["aw"], previous_max_aw(stats, training["t"], dev_id))
        lines.append(
            f"{station_name(devices_map[str(dev_id)]['name'])} "
            f"{best['aw']}/{best['adw']} kg{arrow} · {reps} reps · {quality}%"
        )
    return "\n".join(lines)
