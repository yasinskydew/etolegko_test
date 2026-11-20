import {
  createApi,
  fetchBaseQuery,
  type BaseQueryFn,
  type FetchArgs,
  type FetchBaseQueryError,
} from "@reduxjs/toolkit/query/react";

import { clearToken, getToken } from "@/lib/auth";
import type {
  ApiErrorBody,
  Company,
  CompanyListResponse,
  OfferCatalogResponse,
  Stats,
  StreamAction,
} from "@/lib/types";

const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const rawBaseQuery = fetchBaseQuery({
  baseUrl,
  prepareHeaders: (headers) => {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return headers;
  },
});

const baseQueryWithAuth: BaseQueryFn<
  string | FetchArgs,
  unknown,
  FetchBaseQueryError
> = async (args, api, extra) => {
  const result = await rawBaseQuery(args, api, extra);
  if (result.error?.status === 401) {
    clearToken();
  }
  return result;
};

export function getErrorMessage(error: unknown): string {
  if (!error || typeof error !== "object") return "Request failed";
  const err = error as FetchBaseQueryError;
  const data = err.data as
    | (ApiErrorBody & { detail?: string | { msg?: string }[] })
    | undefined;
  if (data?.message) return data.message;
  if (typeof data?.detail === "string") return data.detail;
  if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
    return data.detail[0].msg;
  }
  if (typeof err.status === "number") return `HTTP ${err.status}`;
  return "Request failed";
}

export function getErrorCode(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined;
  const data = (error as FetchBaseQueryError).data as ApiErrorBody | undefined;
  return data?.error;
}

export const api = createApi({
  reducerPath: "api",
  baseQuery: baseQueryWithAuth,
  tagTypes: ["companies", "company", "offers", "stats"] as const,
  endpoints: (build) => ({
    login: build.mutation<
      { access_token: string; token_type: string },
      { username: string; password: string }
    >({
      query: (body) => ({
        url: "/auth/login",
        method: "POST",
        body,
      }),
    }),

    listCompanies: build.query<
      CompanyListResponse,
      { q?: string; page?: number; page_size?: number }
    >({
      query: ({ q, page = 1, page_size = 20 }) => ({
        url: "/companies",
        params: { q: q || undefined, page, page_size },
      }),
      providesTags: (result) =>
        result
          ? [
              { type: "companies" as const, id: "LIST" },
              ...result.items.map((c) => ({
                type: "company" as const,
                id: c.id,
              })),
            ]
          : [{ type: "companies" as const, id: "LIST" }],
    }),

    getCompany: build.query<Company, number>({
      query: (id) => `/companies/${id}`,
      providesTags: (_r, _e, id) => [{ type: "company", id }],
    }),

    getCompanyStats: build.query<Stats, number>({
      query: (id) => `/companies/${id}/stats`,
      providesTags: (_r, _e, id) => [{ type: "stats", id }],
    }),

    createCompany: build.mutation<
      Company,
      {
        name: string;
        geo_codes: string[];
        offer_id: number;
        idempotencyKey: string;
      }
    >({
      query: ({ idempotencyKey, ...body }) => ({
        url: "/companies",
        method: "POST",
        body,
        headers: { "Idempotency-Key": idempotencyKey },
      }),
      invalidatesTags: [
        { type: "companies", id: "LIST" },
        { type: "company", id: "LIST" },
      ],
    }),

    applyCompany: build.mutation<
      Company,
      {
        companyId: number;
        geo_codes: string[];
        offers: {
          offer_id: number;
          percent: number;
          pinned: boolean;
          removed: boolean;
          position: number;
        }[];
      }
    >({
      query: ({ companyId, ...body }) => ({
        url: `/companies/${companyId}`,
        method: "PUT",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => [
        { type: "company", id: arg.companyId },
        { type: "companies", id: "LIST" },
        { type: "stats", id: arg.companyId },
      ],
    }),

    streamAction: build.mutation<
      Company,
      {
        companyId: number;
        streamId: number;
        action: StreamAction;
        offer_id: number;
        percent?: number;
      }
    >({
      query: ({ companyId, streamId, ...body }) => ({
        url: `/companies/${companyId}/streams/${streamId}/actions`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => [
        { type: "company", id: arg.companyId },
        { type: "companies", id: "LIST" },
        { type: "stats", id: arg.companyId },
      ],
    }),

    pushCompany: build.mutation<Company, number>({
      query: (id) => ({
        url: `/companies/${id}/sync`,
        method: "POST",
      }),
      invalidatesTags: (_r, _e, id) => [
        { type: "company", id },
        { type: "companies", id: "LIST" },
      ],
    }),

    cancelCompany: build.mutation<Company, number>({
      query: (id) => ({
        url: `/companies/${id}/cancel`,
        method: "POST",
      }),
      invalidatesTags: (_r, _e, id) => [
        { type: "company", id },
        { type: "companies", id: "LIST" },
      ],
    }),

    fetchCompany: build.mutation<Company, number>({
      query: (id) => ({
        url: `/companies/${id}/fetch`,
        method: "POST",
      }),
      invalidatesTags: (_r, _e, id) => [
        { type: "company", id },
        { type: "companies", id: "LIST" },
        { type: "stats", id },
      ],
    }),

    patchGeo: build.mutation<
      Company,
      { companyId: number; geo_codes: string[] }
    >({
      query: ({ companyId, ...body }) => ({
        url: `/companies/${companyId}/geo`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_r, _e, arg) => [
        { type: "company", id: arg.companyId },
        { type: "companies", id: "LIST" },
      ],
    }),

    enableCompany: build.mutation<Company, { companyId: number }>({
      query: ({ companyId }) => ({
        url: `/companies/${companyId}/enable`,
        method: "POST",
        // No expected_version after system-update-1; empty JSON body is fine.
        body: {},
      }),
      invalidatesTags: (_r, _e, arg) => [
        { type: "company", id: arg.companyId },
        { type: "companies", id: "LIST" },
      ],
    }),

    disableCompany: build.mutation<Company, { companyId: number }>({
      query: ({ companyId }) => ({
        url: `/companies/${companyId}/disable`,
        method: "POST",
        body: {},
      }),
      invalidatesTags: (_r, _e, arg) => [
        { type: "company", id: arg.companyId },
        { type: "companies", id: "LIST" },
      ],
    }),

    listOffers: build.query<OfferCatalogResponse, { q?: string } | void>({
      query: (arg) => ({
        url: "/offers",
        params: { q: arg && "q" in arg ? arg.q || undefined : undefined },
      }),
      providesTags: [{ type: "offers", id: "LIST" }],
    }),
  }),
});

export const {
  useLoginMutation,
  useListCompaniesQuery,
  useGetCompanyQuery,
  useGetCompanyStatsQuery,
  useCreateCompanyMutation,
  useApplyCompanyMutation,
  useStreamActionMutation,
  usePushCompanyMutation,
  useCancelCompanyMutation,
  useFetchCompanyMutation,
  usePatchGeoMutation,
  useEnableCompanyMutation,
  useDisableCompanyMutation,
  useListOffersQuery,
  useLazyListOffersQuery,
} = api;
