import pytest

T0 = 1794298668


def device(dev_id, t, aw, adw, moves, q, ws=10, d=60):
    return {
        "id": dev_id,
        "t": t,
        "d": d,
        "aw": aw,
        "adw": adw,
        "ws": ws,
        "moves": moves,
        "tr_q": q,
    }


def training(t, devs, plan="Plan A", ws=250, moves=120, d=1800):
    return {
        "training": {"t": t, "d": d, "ws": ws, "moves": moves, "plan_name": plan},
        "devices": devs,
    }


@pytest.fixture
def devices_map():
    return {
        "1": {"name": "Q LEG PRESS"},
        "2": {"name": "Q LAT PULL V2"},
        "3": {"name": "Q ROTATOR KOMBI"},
        "537": {"name": "Q LEG PRESS"},
        "708": {"name": "Q LAT PULL V2"},
        "999": {"name": "Unknown Thing"},
    }
