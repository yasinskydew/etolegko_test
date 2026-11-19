import type { OfferRow } from "./types";

/** Active (non-removed) offers. */
export function activeOffers(offers: OfferRow[]): OfferRow[] {
  return offers.filter((o) => !o.removed);
}

/**
 * Forbid pinning the last unpinned active offer via set_percent/pin
 * when pinned sum would not be 100.
 */
export function canPinOrSetPercent(
  offers: OfferRow[],
  offerId: number,
  nextPercent?: number,
): { ok: true } | { ok: false; reason: string } {
  const active = activeOffers(offers);
  const target = active.find((o) => o.offer_id === offerId);
  if (!target) return { ok: false, reason: "Offer is not active." };

  const othersPinned = active.filter(
    (o) => o.offer_id !== offerId && o.pinned,
  );
  const freeOthers = active.filter(
    (o) => o.offer_id !== offerId && !o.pinned,
  );

  const pinnedSum =
    othersPinned.reduce((s, o) => s + o.percent, 0) +
    (nextPercent ?? target.percent);

  if (freeOthers.length === 0 && pinnedSum !== 100) {
    return {
      ok: false,
      reason: "Cannot pin the last free offer unless pinned shares sum to 100.",
    };
  }

  if (freeOthers.length > 0) {
    const remainder = 100 - pinnedSum;
    if (remainder < freeOthers.length) {
      return {
        ok: false,
        reason: "Not enough remainder for free offers (min 1% each).",
      };
    }
  }

  return { ok: true };
}

export function displayPercent(offer: OfferRow): number {
  return offer.removed ? 0 : offer.percent;
}
