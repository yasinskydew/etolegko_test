import type { OfferRow } from "./types";

/** Active (non-removed) offers. */
export function activeOffers(offers: OfferRow[]): OfferRow[] {
  return offers.filter((o) => !o.removed);
}

/**
 * Validate pin / set_percent against system-update-1 weight rules:
 * pinned sum ≤ 100 (may be < 100); free share the remainder (may be 0%).
 */
export function canPinOrSetPercent(
  offers: OfferRow[],
  offerId: number,
  nextPercent?: number,
): { ok: true } | { ok: false; reason: string } {
  const active = activeOffers(offers);
  const target = active.find((o) => o.offer_id === offerId);
  if (!target) return { ok: false, reason: "Offer is not active." };

  if (nextPercent !== undefined) {
    if (!Number.isInteger(nextPercent) || nextPercent < 1 || nextPercent > 100) {
      return { ok: false, reason: "Share must be an integer from 1 to 100." };
    }
  }

  const othersPinned = active.filter(
    (o) => o.offer_id !== offerId && o.pinned,
  );

  const pinnedSum =
    othersPinned.reduce((s, o) => s + o.percent, 0) +
    (nextPercent ?? target.percent);

  if (pinnedSum > 100) {
    return {
      ok: false,
      reason: "Pinned shares cannot exceed 100%.",
    };
  }

  return { ok: true };
}

export function displayPercent(offer: OfferRow): number {
  return offer.removed ? 0 : offer.percent;
}
