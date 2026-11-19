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
    """Recalculate free shares so participant percents sum to 100.

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
        if pinned_sum != 100:
            raise WeightError("All pinned but sum is not 100")
        return list(offers)

    remainder = 100 - pinned_sum
    if remainder < len(free):
        raise WeightError("Not enough remainder for free offers")

    base, extra = divmod(remainder, len(free))
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
    free_others = [
        o for o in active if o.offer_id != offer_id and not o.pinned
    ]
    pinned_sum_after = sum(o.percent for o in others_pinned) + percent

    if not free_others:
        if pinned_sum_after != 100:
            raise WeightError(
                "Cannot set_percent last free offer unless pinned sum becomes 100"
            )
        return

    if pinned_sum_after > 100:
        raise WeightError("Pinned sum would exceed 100")
    remainder = 100 - pinned_sum_after
    if remainder < len(free_others):
        raise WeightError("Not enough remainder for free offers")


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
