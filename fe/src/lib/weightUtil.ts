import type { OfferRow } from "./types";

export class WeightError extends Error {}

function participants(offers: OfferRow[]): OfferRow[] {
  return offers.filter((o) => !o.removed);
}

/** Mirror BE redistribute for local draft edits. */
export function redistribute(offers: OfferRow[]): OfferRow[] {
  const active = participants(offers);
  if (!active.length) return offers.map((o) => ({ ...o }));

  const pinned = active.filter((o) => o.pinned);
  const free = active.filter((o) => !o.pinned);
  const pinnedSum = pinned.reduce((s, o) => s + o.percent, 0);
  if (pinnedSum > 100) throw new WeightError("Pinned sum exceeds 100");
  if (!free.length) return offers.map((o) => ({ ...o }));

  const remainder = 100 - pinnedSum;
  const base = Math.floor(remainder / free.length);
  const extra = remainder % free.length;
  const freeSorted = [...free].sort(
    (a, b) => a.position - b.position || a.offer_id - b.offer_id,
  );
  const assigned = new Map<number, number>();
  freeSorted.forEach((o, i) => {
    assigned.set(o.offer_id, base + (i < extra ? 1 : 0));
  });

  return offers.map((o) => {
    if (o.removed || o.pinned) return { ...o };
    return { ...o, percent: assigned.get(o.offer_id) ?? o.percent };
  });
}

export function applyAdd(offers: OfferRow[], offerId: number): OfferRow[] {
  const existing = offers.find((o) => o.offer_id === offerId);
  if (existing) {
    if (!existing.removed) throw new WeightError("Offer already active");
    return applyRestore(offers, offerId);
  }
  const nextPos = Math.max(0, ...offers.map((o) => o.position)) + 1;
  return redistribute([
    ...offers,
    {
      offer_id: offerId,
      name: null,
      percent: 1,
      pinned: false,
      removed: false,
      position: nextPos,
    },
  ]);
}

export function applyRemove(offers: OfferRow[], offerId: number): OfferRow[] {
  const updated = offers.map((o) =>
    o.offer_id === offerId ? { ...o, removed: true } : o,
  );
  if (!participants(updated).length) return updated;
  return redistribute(updated);
}

export function applyRestore(offers: OfferRow[], offerId: number): OfferRow[] {
  const updated = offers.map((o) =>
    o.offer_id === offerId ? { ...o, removed: false, pinned: false } : o,
  );
  return redistribute(updated);
}

export function applyPin(offers: OfferRow[], offerId: number): OfferRow[] {
  const updated = offers.map((o) =>
    o.offer_id === offerId ? { ...o, pinned: true } : o,
  );
  const pinnedSum = participants(updated)
    .filter((o) => o.pinned)
    .reduce((s, o) => s + o.percent, 0);
  if (pinnedSum > 100) throw new WeightError("Pinned sum would exceed 100");
  return redistribute(updated);
}

export function applyUnpin(offers: OfferRow[], offerId: number): OfferRow[] {
  return redistribute(
    offers.map((o) =>
      o.offer_id === offerId ? { ...o, pinned: false } : o,
    ),
  );
}

export function applySetPercent(
  offers: OfferRow[],
  offerId: number,
  percent: number,
): OfferRow[] {
  if (!Number.isInteger(percent) || percent < 1 || percent > 100) {
    throw new WeightError("percent must be 1..100");
  }
  const othersPinned = participants(offers).filter(
    (o) => o.offer_id !== offerId && o.pinned,
  );
  const pinnedSum =
    othersPinned.reduce((s, o) => s + o.percent, 0) + percent;
  if (pinnedSum > 100) throw new WeightError("Pinned sum would exceed 100");
  return redistribute(
    offers.map((o) =>
      o.offer_id === offerId
        ? { ...o, percent, pinned: true }
        : o,
    ),
  );
}
