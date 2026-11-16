import { HANDOFF_KEY } from "./handoff.js";

/**
 * Content script entry for https://www.strava.com/upload/select*.
 * @typedef {import("./handoff.js").Handoff} Handoff
 */

const SELECTORS = {
	file: "input[type=file]",
	title: "input[name=name]",
	description:
		".description-container textarea, textarea[class*=mentions__input]",
	descriptionHidden: "input[type=hidden][name=description]",
};
const FILE_TIMEOUT_MS = 30000;
const FORM_TIMEOUT_MS = 120000;
const POLL_MS = 250;

/** @param {number} ms */
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Entry: no handoff -> return; else set file, remove handoff, fill form, verify.
 * @returns {Promise<void>}
 */
async function main() {
	const { [HANDOFF_KEY]: handoff } =
		await chrome.storage.local.get(HANDOFF_KEY);
	if (handoff === undefined) {
		return;
	}
	try {
		setFile(await waitFor(SELECTORS.file, FILE_TIMEOUT_MS), handoff);
		await chrome.storage.local.remove(HANDOFF_KEY);
		setValue(await waitFor(SELECTORS.title, FORM_TIMEOUT_MS), handoff.title);
		setValue(
			await waitFor(SELECTORS.description, FORM_TIMEOUT_MS),
			handoff.description,
		);
		const hidden = document.querySelector(SELECTORS.descriptionHidden);
		if (hidden?.value !== handoff.description) {
			showBanner(`Description not applied. Copy it:\n${handoff.description}`);
		}
	} catch (error) {
		showBanner(error.message);
		throw error;
	}
}

/**
 * Polls for selector; rejects with `${selector} not found after ${s} s`.
 * @param {string} selector
 * @param {number} timeoutMs
 * @returns {Promise<Element>}
 */
async function waitFor(selector, timeoutMs) {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		const el = document.querySelector(selector);
		if (el !== null) {
			return el;
		}
		await sleep(POLL_MS);
	}
	throw new Error(`${selector} not found after ${timeoutMs / 1000} s`);
}

/**
 * DataTransfer with one File, assigns input.files, dispatches bubbling change.
 * @param {HTMLInputElement} input
 * @param {Handoff} handoff
 */
function setFile(input, handoff) {
	const transfer = new DataTransfer();
	transfer.items.add(
		new File([Uint8Array.from(handoff.fit)], handoff.fileName),
	);
	input.files = transfer.files;
	input.dispatchEvent(new Event("change", { bubbles: true }));
}

/**
 * Assigns value, dispatches bubbling input.
 * @param {HTMLInputElement | HTMLTextAreaElement} el
 * @param {string} value
 */
function setValue(el, value) {
	el.value = value;
	el.dispatchEvent(new Event("input", { bubbles: true }));
}

/** @param {string} text */
function showBanner(text) {
	const banner = document.createElement("div");
	banner.textContent = `milon → Strava: ${text}`;
	Object.assign(banner.style, {
		position: "fixed",
		top: "0",
		left: "0",
		right: "0",
		zIndex: "2147483647",
		padding: "8px 16px",
		background: "#fff3cd",
		color: "#000",
		whiteSpace: "pre-wrap",
	});
	document.body.append(banner);
}

main();
