from __future__ import annotations

from app.models import Stream, StreamOffer, StreamOfferSnapshot, StreamType


def offer_tuple(row: StreamOffer | StreamOfferSnapshot) -> tuple:
    return (
        row.offer_id,
        int(row.percent),
        bool(row.pinned),
        bool(row.removed),
        int(row.position),
    )


def compute_stream_sync(stream: Stream) -> str | None:
    if stream.type != StreamType.offers:
        return None
    working = {offer_tuple(o) for o in stream.offers}
    snapshot = {offer_tuple(s) for s in stream.snapshots}
    return "synced" if working == snapshot else "update_mode"


def compute_company_sync(streams: list[Stream], lifecycle: str) -> str | None:
    if lifecycle == "creating":
        return None
    for stream in streams:
        if stream.type == StreamType.offers:
            return compute_stream_sync(stream)
    return None
