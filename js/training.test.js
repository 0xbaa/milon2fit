import assert from "node:assert/strict";
import { test } from "node:test";
import { T0, device, devicesMap, training } from "./test-helpers.js";
import { attendanceMonths, machineName, trainingWindow } from "./training.js";

const EPOCH_2026_10_31_2330Z = 1793489400;

test("attendanceMonths uses the local zone and keeps only premium", () => {
	const att = [
		{ t: EPOCH_2026_10_31_2330Z, type: "p" },
		{ t: T0, type: "p" },
		{ t: T0, type: "tp" },
	];
	assert.deepEqual(attendanceMonths(att), ["2611"]);
});

test("trainingWindow covers the training start and all rounds", () => {
	const stat = training(T0, [
		device(1, T0 - 1, 1, 1, 1, 1),
		device(2, T0 + 500, 1, 1, 1, 1),
	]);
	assert.deepEqual(trainingWindow(stat), [T0 - 1, T0 + 560]);
});

test("machineName returns the name and throws on a missing id", () => {
	assert.equal(machineName(devicesMap, 1), "Q LEG PRESS");
	assert.throws(
		() => machineName(devicesMap, 4242),
		/device 4242 not in devices map/,
	);
});
