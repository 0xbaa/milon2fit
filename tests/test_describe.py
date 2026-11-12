import pytest
from conftest import T0, device, training

from milon_export.describe import build_description, station_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Q LEG PRESS", "Leg Press"),
        ("Q LAT PULL V2", "Lat Pull"),
        ("BACK EXTENSION A", "Back Extension A"),
    ],
)
def test_station_name(raw, expected):
    assert station_name(raw) == expected


def test_groups_stations_in_first_appearance_order(devices_map):
    stat = training(
        T0,
        [
            device(1, T0, 100, 130, 8, 60, ws=20),
            device(2, T0 + 100, 30, 40, 10, 90, ws=10),
            device(1, T0 + 200, 100, 130, 10, 85, ws=30),
        ],
        ws=60,
        moves=28,
        d=180,
    )
    lines = build_description(stat, devices_map, [stat]).splitlines()
    assert lines[0] == "60 kcal · 28 reps · 3 min active · 4 min total · 2.1 t moved"
    assert lines[2] == "Leg Press 100/130 kg · 8+10 reps · 60/85%"
    assert lines[3] == "Lat Pull 30/40 kg · 10 reps · 90%"
    assert len(lines) == 4


def test_shows_max_round_weights(devices_map):
    stat = training(
        T0,
        [device(1, T0, 100, 130, 8, 60), device(1, T0 + 100, 110, 143, 8, 60)],
    )
    assert "Leg Press 110/143 kg" in build_description(stat, devices_map, [stat])


def test_trend_arrows(devices_map):
    old = training(T0 - 1000, [device(1, T0 - 1000, 90, 117, 8, 60)])
    older = training(T0 - 2000, [device(2, T0 - 2000, 99, 99, 8, 60)])
    older2 = training(T0 - 3000, [device(3, T0 - 3000, 20, 26, 8, 60)])
    cur = training(
        T0,
        [
            device(1, T0, 100, 130, 8, 60),
            device(2, T0 + 10, 30, 40, 8, 60),
            device(3, T0 + 20, 20, 26, 8, 60),
        ],
    )
    desc = build_description(cur, devices_map, [older2, older, old, cur])
    lines = desc.splitlines()
    assert lines[2].startswith("Leg Press 100/130 kg ↑ · ")
    assert lines[3].startswith("Lat Pull 30/40 kg ↓ · ")
    assert lines[4].startswith("Rotator Kombi 20/26 kg · ")


def test_no_previous_no_arrow(devices_map):
    cur = training(T0, [device(1, T0, 100, 130, 8, 60)])
    desc = build_description(cur, devices_map, [cur])
    assert "↑" not in desc
    assert "↓" not in desc
