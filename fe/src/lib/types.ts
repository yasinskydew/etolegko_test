export type TrafficStatus = "active" | "disabled";
export type CompanyLifecycle = "creating" | "ready" | "failed";
export type StreamType = "google" | "offers" | "plain";

export type OfferRow = {
  offer_id: number;
  name: string | null;
  percent: number;
  pinned: boolean;
  removed: boolean;
  position: number;
};

export type Stream = {
  id: number;
  type: StreamType;
  position: number;
  offers: OfferRow[];
};

export type Drift = {
  campaign_missing: boolean;
  offers: boolean;
  geo: boolean;
  traffic: boolean;
  streams: boolean;
};

export type Company = {
  id: number;
  name: string;
  lifecycle: CompanyLifecycle;
  traffic_status: TrafficStatus;
  geo_codes: string[];
  streams: Stream[];
  drift: Drift | null;
  reconcile_unavailable: boolean;
};

export type CompanyListItem = {
  id: number;
  name: string;
  lifecycle: CompanyLifecycle;
  traffic_status: TrafficStatus;
  geo_codes: string[];
};

export type CompanyListResponse = {
  items: CompanyListItem[];
  page: number;
  page_size: number;
  total: number;
};

export type Stats = {
  clicks: number | null;
  uniques: number | null;
  bots: number | null;
};

export type OfferCatalogItem = {
  offer_id: number;
  name: string | null;
  country?: string[];
};

export type OfferCatalogResponse = {
  items: OfferCatalogItem[];
};

/** Mirrors backend `ErrorCode`; `network_error` is client-side only. */
export type ApiErrorCode =
  | "unauthorized"
  | "not_found"
  | "method_not_allowed"
  | "name_taken"
  | "idempotency_conflict"
  | "company_not_ready"
  | "campaign_missing"
  | "concurrent_update"
  | "keitaro_not_found"
  | "validation_error"
  | "unknown_geo"
  | "keitaro_bad_gateway"
  | "keitaro_partial_apply"
  | "keitaro_timeout"
  | "internal_error"
  | "network_error";

/** Body of every non-2xx backend response (OpenAPI `ErrorBody`). */
export type ApiErrorBody = {
  error: ApiErrorCode;
  message: string;
  fields?: Record<string, string>;
};
