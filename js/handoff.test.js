import assert from "node:assert/strict";
import { test } from "node:test";
import { ACTIVITY_NAME, buildDescription } from "./describe.js";
import { buildFit } from "./fit.js";
import { fitFileName, toHandoff } from "./handoff.js";
import { T0, decode, device, devicesMap, training } from "./test-helpers.js";

const stat = training(T0, [device(537, T0, 100, 130, 8, 60, { d: 30 })], {
	d: 30,
});
const trainings = { stats: [stat], devicesMap };

test("handoff survives a JSON roundtrip", () => {
	const handoff = JSON.parse(JSON.stringify(toHandoff(trainings, stat)));
	assert.equal(handoff.t, T0);
	assert.equal(handoff.title, ACTIVITY_NAME);
	assert.equal(
		handoff.description,
		buildDescription(stat, devicesMap, trainings.stats),
	);
	assert.deepEqual(handoff.fit, Array.from(buildFit(stat, devicesMap)));
	const data = decode(Uint8Array.from(handoff.fit));
	assert.equal(data.setMesgs.length, 1);
});

test("fitFileName formats local time", () => {
	assert.equal(fitFileName(T0), "milon-2026-11-10-0917.fit");
	assert.equal(fitFileName(1782907200), "milon-2026-07-01-1400.fit");
});
