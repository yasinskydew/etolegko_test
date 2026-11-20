from __future__ import annotations

from dataclasses import dataclass, replace


class WeightError(ValueError):
    """Invalid weight operation."""


@dataclass(frozen=True)
class OfferWeight:
    offer_id: int
    percent: int
    pinned: bool
    removed: bool
    position: int


def participants(offers: list[OfferWeight]) -> list[OfferWeight]:
    return [o for o in offers if not o.removed]


def redistribute(offers: list[OfferWeight]) -> list[OfferWeight]:
    """Recalculate free shares from remainder after pinned.

    Rules (system update 1):
    - pinned sum must be ≤ 100 (never > 100); may be < 100
    - free share (100 − pinned) equally; if pinned = 100 → free get 0%
    - no free and pinned < 100 → leave as-is (Push allowed)
    Empty stream (no participants) is left unchanged.
    Tail remainder goes +1 by ascending position, then offer_id.
    """
    active = participants(offers)
    if not active:
        return list(offers)

    pinned = [o for o in active if o.pinned]
    free = [o for o in active if not o.pinned]
    pinned_sum = sum(o.percent for o in pinned)

    if pinned_sum > 100:
        raise WeightError("Pinned sum exceeds 100")
    if not free:
        # All pinned: sum may be < 100; Push is allowed without forcing 100.
        return list(offers)

    remainder = 100 - pinned_sum
    # Free may receive 0% when pinned already fills 100.
    base, extra = divmod(remainder, len(free)) if free else (0, 0)
    free_sorted = sorted(free, key=lambda o: (o.position, o.offer_id))
    assigned: dict[int, int] = {}
    for i, offer in enumerate(free_sorted):
        assigned[offer.offer_id] = base + (1 if i < extra else 0)

    result: list[OfferWeight] = []
    for offer in offers:
        if offer.removed or offer.pinned:
            result.append(offer)
        else:
            result.append(replace(offer, percent=assigned[offer.offer_id]))
    return result


def validate_set_percent(
    offers: list[OfferWeight],
    offer_id: int,
    percent: int,
) -> None:
    if percent < 1 or percent > 100:
        raise WeightError("percent must be 1..100")

    active = participants(offers)
    target = next((o for o in active if o.offer_id == offer_id), None)
    if target is None:
        raise WeightError("offer is not an active participant")

    others_pinned = [
        o for o in active if o.offer_id != offer_id and o.pinned
    ]
    pinned_sum_after = sum(o.percent for o in others_pinned) + percent

    if pinned_sum_after > 100:
        raise WeightError("Pinned sum would exceed 100")


def apply_add(offers: list[OfferWeight], offer_id: int) -> list[OfferWeight]:
    existing = next((o for o in offers if o.offer_id == offer_id), None)
    if existing is not None:
        if not existing.removed:
            raise WeightError("Offer already active")
        return apply_restore(offers, offer_id)

    next_pos = max((o.position for o in offers), default=0) + 1
    added = OfferWeight(
        offer_id=offer_id,
        percent=1,
        pinned=False,
        removed=False,
        position=next_pos,
    )
    return redistribute([*offers, added])


def apply_remove(offers: list[OfferWeight], offer_id: int) -> list[OfferWeight]:
    found = False
    updated: list[OfferWeight] = []
    for offer in offers:
        if offer.offer_id == offer_id:
            if offer.removed:
                raise WeightError("Offer already removed")
            found = True
            updated.append(replace(offer, removed=True))
        else:
            updated.append(offer)
    if not found:
        raise WeightError("Offer not found")
    if not participants(updated):
        return updated
    return redistribute(updated)


def apply_restore(offers: list[OfferWeight], offer_id: int) -> list[OfferWeight]:
    found = False
    updated: list[OfferWeight] = []
    for offer in offers:
        if offer.offer_id == offer_id:
            if not offer.removed:
                raise WeightError("Offer is not removed")
            found = True
            updated.append(replace(offer, removed=False, pinned=False))
        else:
            updated.append(offer)
    if not found:
        raise WeightError("Offer not found")
    return redistribute(updated)


def apply_pin(offers: list[OfferWeight], offer_id: int) -> list[OfferWeight]:
    updated: list[OfferWeight] = []
    found = False
    for offer in offers:
        if offer.offer_id == offer_id:
            if offer.removed:
                raise WeightError("Cannot pin removed offer")
            found = True
            updated.append(replace(offer, pinned=True))
        else:
            updated.append(offer)
    if not found:
        raise WeightError("Offer not found")
    # Pinning must not leave pinned sum > 100 (e.g. free already hold remainder).
    pinned_sum = sum(
        o.percent for o in participants(updated) if o.pinned
    )
    if pinned_sum > 100:
        raise WeightError("Pinned sum would exceed 100")
    return redistribute(updated)


def apply_unpin(offers: list[OfferWeight], offer_id: int) -> list[OfferWeight]:
    updated: list[OfferWeight] = []
    found = False
    for offer in offers:
        if offer.offer_id == offer_id:
            if offer.removed:
                raise WeightError("Cannot unpin removed offer")
            found = True
            updated.append(replace(offer, pinned=False))
        else:
            updated.append(offer)
    if not found:
        raise WeightError("Offer not found")
    return redistribute(updated)


def apply_set_percent(
    offers: list[OfferWeight],
    offer_id: int,
    percent: int,
) -> list[OfferWeight]:
    validate_set_percent(offers, offer_id, percent)
    updated: list[OfferWeight] = []
    for offer in offers:
        if offer.offer_id == offer_id:
            updated.append(replace(offer, percent=percent, pinned=True))
        else:
            updated.append(offer)
    return redistribute(updated)
