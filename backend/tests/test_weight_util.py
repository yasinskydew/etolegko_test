import pytest

from app.services.weight_util import (
    OfferWeight,
    WeightError,
    apply_add,
    apply_pin,
    apply_remove,
    apply_restore,
    apply_set_percent,
    apply_unpin,
    redistribute,
)


def _o(
    offer_id: int,
    percent: int,
    *,
    pinned: bool = False,
    removed: bool = False,
    position: int | None = None,
) -> OfferWeight:
    return OfferWeight(
        offer_id=offer_id,
        percent=percent,
        pinned=pinned,
        removed=removed,
        position=position if position is not None else offer_id,
    )


def test_empty_stream_untouched() -> None:
    assert redistribute([]) == []


def test_single_offer_gets_100() -> None:
    result = redistribute([_o(1, 1)])
    assert [r.percent for r in result] == [100]


def test_tail_34_33_33() -> None:
    result = redistribute([_o(1, 0, position=1), _o(2, 0, position=2), _o(3, 0, position=3)])
    assert [r.percent for r in result] == [34, 33, 33]
    assert sum(r.percent for r in result) == 100


def test_pin_keeps_percent() -> None:
    offers = [_o(1, 40, pinned=True, position=1), _o(2, 0, position=2), _o(3, 0, position=3)]
    result = redistribute(offers)
    by_id = {r.offer_id: r.percent for r in result}
    assert by_id[1] == 40
    assert by_id[2] + by_id[3] == 60
    assert sum(by_id.values()) == 100


def test_restore_clears_pin() -> None:
    offers = [
        _o(1, 70, pinned=True, position=1),
        _o(2, 30, pinned=True, removed=True, position=2),
    ]
    result = apply_restore(offers, 2)
    restored = next(r for r in result if r.offer_id == 2)
    assert restored.removed is False
    assert restored.pinned is False
    assert sum(r.percent for r in result if not r.removed) == 100


def test_set_percent_last_free_forbidden_unless_100() -> None:
    offers = [
        _o(1, 60, pinned=True, position=1),
        _o(2, 40, pinned=False, position=2),
    ]
    with pytest.raises(WeightError):
        apply_set_percent(offers, 2, 50)


def test_set_percent_last_free_ok_when_sum_100() -> None:
    offers = [
        _o(1, 60, pinned=True, position=1),
        _o(2, 40, pinned=False, position=2),
    ]
    result = apply_set_percent(offers, 2, 40)
    assert all(r.pinned for r in result)
    assert sum(r.percent for r in result) == 100


def test_remove_last_participant_skips_util() -> None:
    offers = [_o(1, 100, position=1)]
    result = apply_remove(offers, 1)
    assert len(result) == 1
    assert result[0].removed is True


def test_add_then_equal_split() -> None:
    offers = [_o(1, 100, position=1)]
    result = apply_add(offers, 2)
    assert sorted(r.percent for r in result) == [50, 50]


def test_pin_and_unpin() -> None:
    offers = [_o(1, 50, position=1), _o(2, 50, position=2)]
    pinned = apply_pin(offers, 1)
    assert next(r for r in pinned if r.offer_id == 1).pinned is True
    unpinned = apply_unpin(pinned, 1)
    assert next(r for r in unpinned if r.offer_id == 1).pinned is False
    assert sum(r.percent for r in unpinned) == 100


def test_add_active_duplicate_raises() -> None:
    offers = [_o(1, 100, position=1)]
    with pytest.raises(WeightError):
        apply_add(offers, 1)
