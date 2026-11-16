import { Decoder, Stream } from "@garmin/fitsdk";

export const T0 = 1794298668;

export function device(id, t, aw, adw, moves, tr_q, { ws = 10, d = 60 } = {}) {
	return { id, t, d, aw, adw, ws, moves, tr_q };
}

export function training(
	t,
	devices,
	{ plan = "Plan A", ws = 250, moves = 120, d = 1800 } = {},
) {
	return {
		training: { t, d, ws, moves, plan_name: plan },
		devices,
	};
}

export const devicesMap = {
	1: { name: "Q LEG PRESS" },
	2: { name: "Q LAT PULL V2" },
	3: { name: "Q ROTATOR KOMBI" },
	537: { name: "Q LEG PRESS" },
	708: { name: "Q LAT PULL V2" },
	999: { name: "Unknown Thing" },
};

export function decode(data) {
	const { messages, errors } = new Decoder(
		Stream.fromByteArray(Array.from(data)),
	).read();
	if (errors.length > 0) {
		throw new Error(`FIT decode errors: ${errors}`);
	}
	return messages;
}
