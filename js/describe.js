import { machineName, trainingWindow } from "./training.js";

/** @typedef {import("./training.js").Stat} Stat */
/** @typedef {import("./training.js").Dev} Dev */
/** @typedef {import("./training.js").DevicesMap} DevicesMap */

const UP = "↑";
const DOWN = "↓";
export const ACTIVITY_NAME = "Boomer Pump Circuit";

/**
 * Display name of a station from the raw device name.
 * @param {string} raw
 * @returns {string}
 */
export function stationName(raw) {
	return raw
		.replace(/^Q /, "")
		.replace(/ V2$/, "")
		.toLowerCase()
		.replace(/(^|[^\p{L}])(\p{L})/gu, (_, sep, c) => sep + c.toUpperCase());
}

/**
 * Device entries grouped by station id, in first-appearance order.
 * @param {Dev[]} devices
 * @returns {Map<number, Dev[]>}
 */
function stationRounds(devices) {
	return Map.groupBy(
		[...devices].sort((a, b) => a.t - b.t),
		(dev) => dev.id,
	);
}

/**
 * Max aw of the latest training before `t` that includes the station; `stats` sorted ascending.
 * @param {Stat[]} stats
 * @param {number} t
 * @param {number} devId
 * @returns {number | null}
 */
function previousMaxAw(stats, t, devId) {
	const prev = stats.findLast(
		(stat) =>
			stat.training.t < t && stat.devices.some((dev) => dev.id === devId),
	);
	if (prev === undefined) {
		return null;
	}
	return Math.max(
		...prev.devices.filter((dev) => dev.id === devId).map((dev) => dev.aw),
	);
}

/**
 * @param {number} current
 * @param {number | null} previous
 * @returns {string}
 */
function trend(current, previous) {
	if (previous === null || current === previous) {
		return "";
	}
	return current > previous ? ` ${UP}` : ` ${DOWN}`;
}

/**
 * One decimal, rounding exact ties to even like Python's format.
 * @param {number} value
 * @returns {string}
 */
function fixed1(value) {
	const tie = Number.isInteger(value * 4) && !Number.isInteger(value * 10);
	if (!tie) {
		return value.toFixed(1);
	}
	const low = Math.floor(value * 10);
	return ((low % 2 === 0 ? low : low + 1) / 10).toFixed(1);
}

/**
 * Same text as describe.py build_description; `stats` sorted ascending by training.t.
 * @param {Stat} stat
 * @param {DevicesMap} devicesMap
 * @param {Stat[]} stats
 * @returns {string}
 */
export function buildDescription(stat, devicesMap, stats) {
	const { training } = stat;
	const [start, end] = trainingWindow(stat);
	const volume =
		stat.devices.reduce((sum, dev) => sum + dev.aw * dev.moves, 0) / 1000;
	const lines = [
		`${training.ws} kcal · ${training.moves} reps · ` +
			`${Math.floor(training.d / 60)} min active · ${Math.floor((end - start) / 60)} min total · ` +
			`${fixed1(volume)} t moved`,
		"",
	];
	for (const [devId, rounds] of stationRounds(stat.devices)) {
		const best = rounds.reduce((a, b) => (b.aw > a.aw ? b : a));
		const reps = rounds.map((r) => r.moves).join("+");
		const quality = rounds.map((r) => r.tr_q).join("/");
		const arrow = trend(best.aw, previousMaxAw(stats, training.t, devId));
		lines.push(
			`${stationName(machineName(devicesMap, devId))} ` +
				`${best.aw}/${best.adw} kg${arrow} · ${reps} reps · ${quality}%`,
		);
	}
	return lines.join("\n");
}
