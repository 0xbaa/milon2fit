import { HANDOFF_KEY, SENT_KEY, toHandoff } from "./handoff.js";
import { attendanceMonths } from "./training.js";

/**
 * Content script entry for https://www.milonme.com/*.
 * @typedef {import("./training.js").Stat} Stat
 * @typedef {import("./handoff.js").Handoff} Handoff
 * @typedef {import("./handoff.js").Trainings} Trainings
 */

const API = "https://www.milonme.com/api/";
const UPLOAD_URL = "https://www.strava.com/upload/select";

/**
 * GET https://www.milonme.com/api/<path>; throws Error(`${status} ${path}`) on non-2xx.
 * @param {string} path
 * @returns {Promise<unknown>}
 */
async function milonGet(path) {
	const resp = await fetch(`${API}${path}`);
	if (!resp.ok) {
		throw new Error(`${resp.status} ${path}`);
	}
	return resp.json();
}

/**
 * Profile, home, devices, premium months; stats sorted ascending.
 * @returns {Promise<Trainings>}
 */
async function fetchTrainings() {
	const profile = await milonGet("user/profile");
	const sid = profile._sid;
	const uid = profile.id;
	const home = await milonGet(`user/stats/home/${sid}/${uid}`);
	const devicesMap = await milonGet(`devices/${sid}`);
	const stats = [];
	for (const month of attendanceMonths(home.attendance)) {
		const data = await milonGet(`user/stats/premium/${sid}/${uid}/${month}`);
		stats.push(...data.stats);
	}
	stats.sort((a, b) => a.training.t - b.training.t);
	return { stats, devicesMap };
}

/** Appends the fixed "milon → Strava" button; click toggles the panel. */
function mountButton() {
	const button = document.createElement("button");
	button.textContent = "milon → Strava";
	Object.assign(button.style, {
		position: "fixed",
		right: "16px",
		bottom: "16px",
		zIndex: "2147483647",
		padding: "8px 12px",
		cursor: "pointer",
	});
	const panel = document.createElement("div");
	panel.hidden = true;
	Object.assign(panel.style, {
		position: "fixed",
		right: "16px",
		bottom: "56px",
		zIndex: "2147483647",
		width: "360px",
		maxHeight: "70vh",
		overflowY: "auto",
		padding: "8px",
		background: "#fff",
		color: "#000",
		border: "1px solid #888",
		font: "14px sans-serif",
	});
	button.addEventListener("click", async () => {
		panel.hidden = !panel.hidden;
		if (!panel.hidden) {
			await openPanel(panel);
		}
	});
	document.body.append(panel, button);
}

/**
 * Fetches trainings and sent, renders rows newest first; errors go into the panel text.
 * @param {HTMLElement} panel
 * @returns {Promise<void>}
 */
async function openPanel(panel) {
	panel.textContent = "Loading...";
	try {
		const trainings = await fetchTrainings();
		const { [SENT_KEY]: sentList } = await chrome.storage.local.get({
			[SENT_KEY]: [],
		});
		const sent = new Set(sentList);
		const rows = trainings.stats
			.toReversed()
			.map((stat) => trainingRow(trainings, stat, sent));
		panel.replaceChildren(...rows);
	} catch (error) {
		panel.textContent = error.message;
		throw error;
	}
}

/**
 * @param {string} text
 * @param {string} href
 * @returns {HTMLAnchorElement}
 */
function link(text, href) {
	const a = document.createElement("a");
	a.textContent = text;
	a.href = href;
	a.style.marginLeft = "8px";
	return a;
}

/**
 * @param {Trainings} trainings
 * @param {Stat} stat
 * @param {Set<number>} sent
 * @returns {HTMLElement}
 */
function trainingRow(trainings, stat, sent) {
	const { t, ws } = stat.training;
	const stations = new Set(stat.devices.map((dev) => dev.id)).size;
	const row = document.createElement("div");
	row.style.padding = "4px 0";
	const label = document.createElement("span");
	label.textContent = `${new Date(t * 1000).toLocaleString()} · ${stations} stations · ${ws} kcal`;
	const mark = document.createElement("span");
	mark.textContent = " sent";
	mark.hidden = !sent.has(t);
	const error = document.createElement("div");
	error.hidden = true;
	/** @param {unknown} e */
	const fail = (e) => {
		error.textContent = e.message;
		error.hidden = false;
		throw e;
	};
	const strava = link("Strava", UPLOAD_URL);
	strava.target = "_blank";
	strava.addEventListener("click", (event) => {
		let handoff;
		try {
			handoff = toHandoff(trainings, stat);
		} catch (e) {
			event.preventDefault();
			fail(e);
		}
		sendToStrava(handoff, sent)
			.then(() => {
				mark.hidden = false;
			})
			.catch(fail);
	});
	const fit = link("FIT", "#");
	fit.addEventListener("click", (event) => {
		event.preventDefault();
		try {
			downloadFit(toHandoff(trainings, stat));
		} catch (e) {
			fail(e);
		}
	});
	row.append(label, mark, strava, fit, error);
	return row;
}

/**
 * Click handler of the "Strava" link: adds t to `sent`, stores handoff and sent in one write.
 * @param {Handoff} handoff
 * @param {Set<number>} sent
 * @returns {Promise<void>}
 */
async function sendToStrava(handoff, sent) {
	sent.add(handoff.t);
	await chrome.storage.local.set({
		[HANDOFF_KEY]: handoff,
		[SENT_KEY]: [...sent],
	});
}

/**
 * Blob plus <a download> in the page.
 * @param {Handoff} handoff
 */
function downloadFit(handoff) {
	const url = URL.createObjectURL(new Blob([Uint8Array.from(handoff.fit)]));
	const a = document.createElement("a");
	a.href = url;
	a.download = handoff.fileName;
	document.body.append(a);
	a.click();
	a.remove();
	setTimeout(() => URL.revokeObjectURL(url), 1000);
}

mountButton();
