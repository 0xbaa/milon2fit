/**
 * @typedef {{t: number, d: number, ws: number, moves: number}} Training
 * @typedef {{id: number, t: number, d: number, aw: number, adw: number, ws: number, moves: number, tr_q: number}} Dev
 * @typedef {{training: Training, devices: Dev[]}} Stat
 * @typedef {Record<string, {name: string}>} DevicesMap
 * @typedef {{t: number, type: string}} AttendanceEntry
 */

/**
 * Wall-clock [start, end] epochs covering the training and all its rounds.
 * @param {Stat} stat
 * @returns {[number, number]}
 */
export function trainingWindow(stat) {
	if (stat.devices.length === 0) {
		throw new Error(`training ${stat.training.t} has no devices`);
	}
	const start = Math.min(stat.training.t, ...stat.devices.map((dev) => dev.t));
	const end = Math.max(...stat.devices.map((dev) => dev.t + dev.d));
	return [start, end];
}

/**
 * Distinct YYMM (browser zone) of premium ("p") entries, sorted; warns on skipped entries.
 * @param {AttendanceEntry[]} attendance
 * @returns {string[]}
 */
export function attendanceMonths(attendance) {
	const months = new Set();
	let skipped = 0;
	for (const entry of attendance) {
		if (entry.type !== "p") {
			skipped += 1;
			continue;
		}
		const date = new Date(entry.t * 1000);
		const year = String(date.getFullYear() % 100).padStart(2, "0");
		const month = String(date.getMonth() + 1).padStart(2, "0");
		months.add(`${year}${month}`);
	}
	if (skipped > 0) {
		console.warn(`skipped ${skipped} non-premium attendance entries`);
	}
	return [...months].sort();
}

/**
 * Machine name of a device id.
 * @param {DevicesMap} devicesMap
 * @param {number} id
 * @returns {string}
 */
export function machineName(devicesMap, id) {
	const device = devicesMap[String(id)];
	if (device === undefined) {
		throw new Error(`device ${id} not in devices map`);
	}
	return device.name;
}
