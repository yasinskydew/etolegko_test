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

export type ApiError = { status: number | "NETWORK"; data: ApiErrorBody };

function isApiErrorBody(data: unknown): data is ApiErrorBody {
  return (
    !!data &&
    typeof data === "object" &&
    typeof (data as ApiErrorBody).error === "string" &&
    typeof (data as ApiErrorBody).message === "string"
  );
}

/** Every failed request ends up as `{ status, data: ApiErrorBody }`. */
function toApiError(error: FetchBaseQueryError): ApiError {
  if (typeof error.status === "number") {
    return {
      status: error.status,
      data: isApiErrorBody(error.data)
        ? error.data
        : { error: "internal_error", message: `HTTP ${error.status}` },
    };
  }
  if (error.status === "PARSING_ERROR") {
    return {
      status: error.originalStatus,
      data: { error: "internal_error", message: `HTTP ${error.originalStatus}` },
    };
  }
  return {
    status: "NETWORK",
    data: {
      error: "network_error",
      message: "Network error. Check your connection and try again.",
    },
  };
}

const baseQueryWithAuth: BaseQueryFn<string | FetchArgs, unknown, ApiError> = async (
  args,
  api,
  extra,
) => {
  const result = await rawBaseQuery(args, api, extra);
  if (!result.error) return { data: result.data, meta: result.meta };
  const error = toApiError(result.error);
  if (error.status === 401) {
    clearToken();
  }
  return { error, meta: result.meta };
};

function apiErrorBody(error: unknown): ApiErrorBody | undefined {
  if (!error || typeof error !== "object") return undefined;
  const data = (error as Partial<ApiError>).data;
  return isApiErrorBody(data) ? data : undefined;
}

export function getErrorMessage(error: unknown): string {
  return apiErrorBody(error)?.message ?? "Request failed";
}

export function getErrorCode(error: unknown): ApiErrorBody["error"] | undefined {
  return apiErrorBody(error)?.error;
}

export function getFieldErrors(error: unknown): Record<string, string> {
  return apiErrorBody(error)?.fields ?? {};
}

/** `message` plus per-field details, for toasts and inline alerts. */
export function describeError(error: unknown): string {
  const details = Object.entries(getFieldErrors(error)).map(
    ([field, text]) => `${field}: ${text}`,
  );
  return [getErrorMessage(error), ...details].join(" ");
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

    enableCompany: build.mutation<Company, { companyId: number }>({
      query: ({ companyId }) => ({
        url: `/companies/${companyId}/enable`,
        method: "POST",
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
  useFetchCompanyMutation,
  useEnableCompanyMutation,
  useDisableCompanyMutation,
  useListOffersQuery,
  useLazyListOffersQuery,
} = api;
