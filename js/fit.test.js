import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { Profile, Utils } from "@garmin/fitsdk";
import { ACTIVITY_NAME } from "./describe.js";
import {
	RESOLVED_RULES,
	buildFit,
	camel,
	exerciseFor,
	resolveRules,
} from "./fit.js";
import { T0, decode, device, devicesMap, training } from "./test-helpers.js";

const TYPES = Profile.types;
const ts = (date) => date.getTime() / 1000;

function exerciseName(category, subtype) {
	return subtype === null ? "" : TYPES[`${category}ExerciseName`][subtype];
}

test("camel", () => {
	assert.equal(camel("hip_stability"), "hipStability");
	assert.equal(camel("leg_press"), "legPress");
	assert.equal(camel("core"), "core");
});

test("rule keywords are uppercase", () => {
	for (const [keywords] of RESOLVED_RULES) {
		assert.deepEqual(
			keywords,
			keywords.map((k) => k.toUpperCase()),
		);
	}
});

test("mapping of all milon machines", () => {
	const rows = readFileSync(
		new URL("../tests/fixtures/milon_machines.tsv", import.meta.url),
		"utf8",
	)
		.split("\n")
		.filter((line) => line !== "");
	assert.equal(rows.length, 181);
	for (const row of rows) {
		const [machine, category, name] = row.split("\t");
		const [actualCategory, subtype] = exerciseFor(machine);
		assert.equal(actualCategory, camel(category), machine);
		assert.equal(
			exerciseName(actualCategory, subtype),
			name === "" ? "" : camel(name),
			machine,
		);
	}
});

test("unmapped machine is unknown", () => {
	assert.deepEqual(exerciseFor("Unknown Thing"), ["unknown", null]);
});

test("resolveRules throws on an unknown name", () => {
	assert.throws(() =>
		resolveRules([{ keywords: ["X"], category: "squat", name: "bogus_name" }]),
	);
	assert.throws(() =>
		resolveRules([{ keywords: ["X"], category: "bogus", name: null }]),
	);
});

test("build fit roundtrip", () => {
	const stat = training(
		T0,
		[
			device(708, T0 + 100, 30, 40, 10, 90),
			device(537, T0, 100, 130, 8, 60, { ws: 20 }),
		],
		{ ws: 250, d: 120 },
	);
	const data = decode(buildFit(stat, devicesMap));
	const session = data.sessionMesgs[0];
	assert.equal(session.totalCalories, 250);
	assert.equal(session.totalElapsedTime, 160);
	assert.equal(session.totalTimerTime, 120);
	assert.equal(session.subSport, "strengthTraining");
	assert.equal(data.fileIdMesgs[0].type, "activity");
	assert.deepEqual(
		data.lapMesgs.map((lap) => lap.totalCalories),
		[20, 10],
	);
	const sets = data.setMesgs;
	assert.deepEqual(
		sets.map((s) => s.repetitions),
		[8, 10],
	);
	assert.equal(sets[0].weight, 100);
	assert.equal(ts(sets[0].startTime), T0);
	assert.deepEqual(sets[0].category, ["squat"]);
	assert.equal(TYPES.squatExerciseName[sets[0].categorySubtype[0]], "legPress");
	assert.deepEqual(sets[1].category, ["pullUp"]);
});

test("session spans all sets", () => {
	const stat = training(
		T0,
		[
			device(537, T0 - 1, 100, 130, 8, 60),
			device(708, T0 + 500, 30, 40, 10, 90),
		],
		{ d: 100 },
	);
	const data = decode(buildFit(stat, devicesMap));
	const session = data.sessionMesgs[0];
	assert.equal(ts(session.startTime), T0 - 1);
	assert.equal(session.totalElapsedTime, 561);
	assert.equal(session.totalTimerTime, 100);
	assert.equal(ts(session.timestamp), T0 + 560);
	for (const lap of data.lapMesgs) {
		assert.ok(lap.startTime >= session.startTime);
		assert.ok(lap.timestamp <= session.timestamp);
	}
	const stops = data.eventMesgs.filter((e) => e.eventType === "stopAll");
	assert.equal(ts(stops[0].timestamp), ts(session.timestamp));
	assert.equal(ts(data.activityMesgs[0].timestamp), ts(session.timestamp));
});

test("one record per distinct timestamp", () => {
	const stat = training(
		T0,
		[
			device(537, T0, 100, 130, 8, 60, { d: 30 }),
			device(708, T0 + 30, 30, 40, 8, 60, { d: 30 }),
		],
		{ d: 60 },
	);
	const records = decode(buildFit(stat, devicesMap)).recordMesgs;
	assert.deepEqual(
		records.map((r) => ts(r.timestamp)),
		[T0, T0 + 30, T0 + 60],
	);
});

test("timer intervals sum to active time", () => {
	const stat = training(
		T0,
		[
			device(537, T0, 100, 130, 8, 60, { d: 30 }),
			device(708, T0 + 100, 30, 40, 8, 60, { d: 20 }),
		],
		{ d: 50 },
	);
	const events = decode(buildFit(stat, devicesMap)).eventMesgs.filter(
		(e) => e.event === "timer",
	);
	assert.deepEqual(
		events.map((e) => e.eventType),
		["start", "stop", "start", "stopAll"],
	);
	const stamps = events.map((e) => ts(e.timestamp));
	const active = stamps[1] - stamps[0] + (stamps[3] - stamps[2]);
	assert.equal(active, stat.training.d);
});

for (const [epoch, offset] of [
	[T0, 3600],
	[1782907200, 7200],
]) {
	test(`activity local timestamp uses the zone offset ${offset}`, () => {
		const stat = training(epoch, [
			device(537, epoch, 100, 130, 8, 60, { d: 30 }),
		]);
		const activity = decode(buildFit(stat, devicesMap)).activityMesgs[0];
		const utc = Utils.convertDateToDateTime(activity.timestamp);
		assert.equal(activity.localTimestamp - utc, offset);
	});
}

test("exercise follows machine name not device id", () => {
	const stat = training(T0, [device(532, T0, 100, 130, 8, 60)]);
	const sets = decode(
		buildFit(stat, { 532: { name: "Q LEG PRESS" } }),
	).setMesgs;
	assert.deepEqual(sets[0].category, ["squat"]);
	assert.equal(TYPES.squatExerciseName[sets[0].categorySubtype[0]], "legPress");
});

test("category-only station has no subtype", () => {
	const stat = training(T0, [device(532, T0, 46, 60, 10, 99)]);
	const sets = decode(
		buildFit(stat, { 532: { name: "Q CHEST PRESS" } }),
	).setMesgs;
	assert.deepEqual(sets[0].category, ["benchPress"]);
	assert.equal("categorySubtype" in sets[0], false);
});

test("unmapped station has category unknown", () => {
	const stat = training(T0, [device(999, T0, 6, 8, 10, 90)]);
	const data = decode(buildFit(stat, devicesMap));
	assert.deepEqual(data.setMesgs[0].category, ["unknown"]);
});

test("activity name in sport and workout messages", () => {
	const stat = training(T0, [device(537, T0, 100, 130, 8, 60, { d: 30 })]);
	const data = decode(buildFit(stat, devicesMap));
	const sport = data.sportMesgs[0];
	const workout = data.workoutMesgs[0];
	assert.equal(sport.name, ACTIVITY_NAME);
	assert.equal(workout.wktName, ACTIVITY_NAME);
	assert.equal(sport.sport, "training");
	assert.equal(workout.sport, "training");
	assert.equal(sport.subSport, "strengthTraining");
	assert.equal(workout.subSport, "strengthTraining");
});
