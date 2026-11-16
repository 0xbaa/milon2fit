import { ACTIVITY_NAME, buildDescription } from "./describe.js";
import { buildFit } from "./fit.js";

/**
 * @typedef {import("./training.js").Stat} Stat
 * @typedef {import("./training.js").DevicesMap} DevicesMap
 * @typedef {{t: number, fileName: string, fit: number[], title: string, description: string}} Handoff
 *   One training as handed to the Strava tab; JSON-safe for storage.local in both browsers.
 * @typedef {{stats: Stat[], devicesMap: DevicesMap}} Trainings
 *   All trainings of the user, stats ascending by training.t.
 */

export const HANDOFF_KEY = "handoff";
export const SENT_KEY = "sent";

/**
 * Handoff for one training.
 * @param {Trainings} trainings
 * @param {Stat} stat
 * @returns {Handoff}
 */
export function toHandoff(trainings, stat) {
	const { t } = stat.training;
	return {
		t,
		fileName: fitFileName(t),
		fit: Array.from(buildFit(stat, trainings.devicesMap)),
		title: ACTIVITY_NAME,
		description: buildDescription(stat, trainings.devicesMap, trainings.stats),
	};
}

/**
 * `milon-YYYY-MM-DD-HHMM.fit`, browser-zone local time of training.t.
 * @param {number} t
 * @returns {string}
 */
export function fitFileName(t) {
	const d = new Date(t * 1000);
	const pad = (n) => String(n).padStart(2, "0");
	const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
	return `milon-${date}-${pad(d.getHours())}${pad(d.getMinutes())}.fit`;
}
