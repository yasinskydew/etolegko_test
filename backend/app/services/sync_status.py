from __future__ import annotations

from app.models import Stream, StreamType


def compute_stream_sync(stream: Stream) -> str | None:
    """Local draft lives in FE; DB state is always treated as synced."""
    if stream.type != StreamType.offers:
        return None
    return "synced"


def compute_company_sync(streams: list[Stream], lifecycle: str) -> str | None:
    if lifecycle == "creating":
        return None
    for stream in streams:
        if stream.type == StreamType.offers:
            return compute_stream_sync(stream)
    return None
