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


def previous_max_aw(history: list[dict], t: int, dev_id: int) -> int | None:
    """Max aw of the latest training before `t` that includes the station."""
    for stat in sorted(history, key=lambda s: s["training"]["t"], reverse=True):
        if stat["training"]["t"] >= t:
            continue
        aws = [d["aw"] for d in stat["devices"] if d["id"] == dev_id]
        if aws:
            return max(aws)
    return None


def trend(current: int, previous: int | None) -> str:
    if previous is None or current == previous:
        return ""
    return f" {UP}" if current > previous else f" {DOWN}"


def build_description(stat: dict, devices_map: dict, history: list[dict]) -> str:
    training = stat["training"]
    volume = sum(d["aw"] * d["moves"] for d in stat["devices"]) / 1000
    lines = [
        f"{training['ws']} kcal · {training['moves']} reps · "
        f"{training['d'] // 60} min · {volume:.1f} t moved",
        "",
    ]
    for dev_id, rounds in station_rounds(stat["devices"]).items():
        best = max(rounds, key=lambda d: d["aw"])
        reps = "+".join(str(r["moves"]) for r in rounds)
        quality = "/".join(str(r["tr_q"]) for r in rounds)
        arrow = trend(best["aw"], previous_max_aw(history, training["t"], dev_id))
        lines.append(
            f"{station_name(devices_map[str(dev_id)]['name'])} "
            f"{best['aw']}/{best['adw']} kg · {reps} reps · {quality}%{arrow}"
        )
    return "\n".join(lines)
