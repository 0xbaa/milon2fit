import { Encoder, Profile, Utils } from "@garmin/fitsdk";
import rules from "../src/milon_export/exercise_rules.json" with {
	type: "json",
};
import { ACTIVITY_NAME } from "./describe.js";
import { machineName, trainingWindow } from "./training.js";

/** @typedef {import("./training.js").Stat} Stat */
/** @typedef {import("./training.js").Dev} Dev */
/** @typedef {import("./training.js").DevicesMap} DevicesMap */

const { MesgNum, types } = Profile;
const SPORT = { sport: "training", subSport: "strengthTraining" };

/**
 * snake_case FIT profile name to the JS SDK camelCase form.
 * @param {string} snake
 * @returns {string}
 */
export function camel(snake) {
	return snake.replace(/_([a-z0-9])/g, (_, c) => c.toUpperCase());
}

/**
 * Resolves rule objects to SDK numbers; unknown categories or names throw.
 * @param {{keywords: string[], category: string, name: string | null}[]} ruleList
 * @returns {[keywords: string[], category: string, subtype: number | null][]}
 */
export function resolveRules(ruleList) {
	return ruleList.map(({ keywords, category, name }) => {
		const cat = camel(category);
		if (!Object.values(types.exerciseCategory).includes(cat)) {
			throw new Error(`unknown FIT exercise category ${category}`);
		}
		if (name === null) {
			return [keywords, cat, null];
		}
		const names = types[`${cat}ExerciseName`];
		const found = Object.entries(names ?? {}).find(
			([, value]) => value === camel(name),
		);
		if (found === undefined) {
			throw new Error(`unknown FIT exercise name ${category}/${name}`);
		}
		return [keywords, cat, Number(found[0])];
	});
}

/** Rules from exercise_rules.json resolved to SDK numbers at module load; unknown names throw. */
export const RESOLVED_RULES = resolveRules(rules);

/**
 * FIT category (camelCase) and exercise-name number for a milon machine name; ["unknown", null] if no rule.
 * @param {string} machine
 * @returns {[string, number | null]}
 */
export function exerciseFor(machine) {
	const upper = machine.toUpperCase();
	for (const [keywords, category, subtype] of RESOLVED_RULES) {
		if (keywords.some((keyword) => upper.includes(keyword))) {
			return [category, subtype];
		}
	}
	return ["unknown", null];
}

/** @param {number} t */
const utc = (t) => new Date(t * 1000);

/** @param {number} t @param {"start" | "stop" | "stopAll"} eventType */
function timerMesg(t, eventType) {
	return {
		mesgNum: MesgNum.EVENT,
		timestamp: utc(t),
		event: "timer",
		eventType,
	};
}

/**
 * @param {number} index
 * @param {Dev} dev
 * @param {string} machine
 */
function setMesg(index, dev, machine) {
	const [category, subtype] = exerciseFor(machine);
	return {
		mesgNum: MesgNum.SET,
		timestamp: utc(dev.t + dev.d),
		startTime: utc(dev.t),
		duration: dev.d,
		repetitions: dev.moves,
		weight: dev.aw,
		setType: "active",
		category: [category],
		messageIndex: index,
		...(subtype === null ? {} : { categorySubtype: [subtype] }),
	};
}

/**
 * @param {number} index
 * @param {Dev} dev
 */
function lapMesg(index, dev) {
	return {
		mesgNum: MesgNum.LAP,
		messageIndex: index,
		timestamp: utc(dev.t + dev.d),
		startTime: utc(dev.t),
		totalElapsedTime: dev.d,
		totalTimerTime: dev.d,
		totalCalories: dev.ws,
		...SPORT,
	};
}

/**
 * Same messages, order and values as fit.py build_fit.
 * @param {Stat} stat
 * @param {DevicesMap} devicesMap
 * @returns {Uint8Array}
 */
export function buildFit(stat, devicesMap) {
	const { training } = stat;
	const [startT, endT] = trainingWindow(stat);
	const start = utc(startT);
	const end = utc(endT);
	const offset = -end.getTimezoneOffset() * 60;
	const devs = [...stat.devices].sort((a, b) => a.t - b.t);
	const pending = [
		...new Set([startT, ...devs.flatMap((dev) => [dev.t, dev.t + dev.d])]),
	].sort((a, b) => a - b);
	const encoder = new Encoder();

	/** @param {number} upto */
	const writeRecords = (upto) => {
		while (pending.length > 0 && pending[0] <= upto) {
			encoder.writeMesg({
				mesgNum: MesgNum.RECORD,
				timestamp: utc(pending.shift()),
			});
		}
	};

	encoder.writeMesg({
		mesgNum: MesgNum.FILE_ID,
		type: "activity",
		manufacturer: "development",
		product: 0,
		timeCreated: start,
	});
	encoder.writeMesg({ mesgNum: MesgNum.SPORT, ...SPORT, name: ACTIVITY_NAME });
	encoder.writeMesg({
		mesgNum: MesgNum.WORKOUT,
		...SPORT,
		wktName: ACTIVITY_NAME,
	});
	devs.forEach((dev, index) => {
		writeRecords(dev.t);
		encoder.writeMesg(timerMesg(dev.t, "start"));
		writeRecords(dev.t + dev.d);
		encoder.writeMesg(setMesg(index, dev, machineName(devicesMap, dev.id)));
		encoder.writeMesg(lapMesg(index, dev));
		const last = index === devs.length - 1;
		encoder.writeMesg(timerMesg(dev.t + dev.d, last ? "stopAll" : "stop"));
	});
	encoder.writeMesg({
		mesgNum: MesgNum.SESSION,
		messageIndex: 0,
		timestamp: end,
		startTime: start,
		totalElapsedTime: endT - startT,
		totalTimerTime: training.d,
		totalCalories: training.ws,
		...SPORT,
		firstLapIndex: 0,
		numLaps: devs.length,
	});
	encoder.writeMesg({
		mesgNum: MesgNum.ACTIVITY,
		timestamp: end,
		localTimestamp: Utils.convertDateToDateTime(end) + offset,
		totalTimerTime: training.d,
		numSessions: 1,
		type: "manual",
		event: "activity",
		eventType: "stop",
	});
	return encoder.close();
}
