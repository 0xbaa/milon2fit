import assert from "node:assert/strict";
import { test } from "node:test";
import { buildDescription, stationName } from "./describe.js";
import { T0, device, devicesMap, training } from "./test-helpers.js";

test("stationName", () => {
	assert.equal(stationName("Q LEG PRESS"), "Leg Press");
	assert.equal(stationName("Q LAT PULL V2"), "Lat Pull");
	assert.equal(stationName("BACK EXTENSION A"), "Back Extension A");
});

test("groups stations in first-appearance order", () => {
	const stat = training(
		T0,
		[
			device(1, T0, 100, 130, 8, 60, { ws: 20 }),
			device(2, T0 + 100, 30, 40, 10, 90, { ws: 10 }),
			device(1, T0 + 200, 100, 130, 10, 85, { ws: 30 }),
		],
		{ ws: 60, moves: 28, d: 180 },
	);
	const lines = buildDescription(stat, devicesMap, [stat]).split("\n");
	assert.equal(
		lines[0],
		"60 kcal · 28 reps · 3 min active · 4 min total · 2.1 t moved",
	);
	assert.equal(lines[2], "Leg Press 100/130 kg · 8+10 reps · 60/85%");
	assert.equal(lines[3], "Lat Pull 30/40 kg · 10 reps · 90%");
	assert.equal(lines.length, 4);
});

test("shows max round weights", () => {
	const stat = training(T0, [
		device(1, T0, 100, 130, 8, 60),
		device(1, T0 + 100, 110, 143, 8, 60),
	]);
	assert.ok(
		buildDescription(stat, devicesMap, [stat]).includes("Leg Press 110/143 kg"),
	);
});

test("trend arrows", () => {
	const old = training(T0 - 1000, [device(1, T0 - 1000, 90, 117, 8, 60)]);
	const older = training(T0 - 2000, [device(2, T0 - 2000, 99, 99, 8, 60)]);
	const older2 = training(T0 - 3000, [device(3, T0 - 3000, 20, 26, 8, 60)]);
	const cur = training(T0, [
		device(1, T0, 100, 130, 8, 60),
		device(2, T0 + 10, 30, 40, 8, 60),
		device(3, T0 + 20, 20, 26, 8, 60),
	]);
	const lines = buildDescription(cur, devicesMap, [
		older2,
		older,
		old,
		cur,
	]).split("\n");
	assert.ok(lines[2].startsWith("Leg Press 100/130 kg ↑ · "));
	assert.ok(lines[3].startsWith("Lat Pull 30/40 kg ↓ · "));
	assert.ok(lines[4].startsWith("Rotator Kombi 20/26 kg · "));
});

test("no previous training gives no arrow", () => {
	const cur = training(T0, [device(1, T0, 100, 130, 8, 60)]);
	const desc = buildDescription(cur, devicesMap, [cur]);
	assert.ok(!desc.includes("↑"));
	assert.ok(!desc.includes("↓"));
});

test("volume rounds exact ties to even like Python", () => {
	const stat = training(T0, [device(1, T0, 150, 195, 15, 60)]);
	const header = buildDescription(stat, devicesMap, [stat]).split("\n")[0];
	assert.ok(header.endsWith("2.2 t moved"), header);
});
