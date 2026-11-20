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

export type ApiErrorBody = {
  error: string;
  message: string;
  fields?: Record<string, string>;
};
