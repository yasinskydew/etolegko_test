import enum


class CompanyLifecycle(str, enum.Enum):
    creating = "creating"
    ready = "ready"


class TrafficStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class StreamType(str, enum.Enum):
    google = "google"
    offers = "offers"
    plain = "plain"
