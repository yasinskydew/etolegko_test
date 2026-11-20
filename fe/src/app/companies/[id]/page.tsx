"use client";

import {
  Box,
  Button,
  Field,
  Heading,
  HStack,
  Input,
  SimpleGrid,
  Stack,
  Text,
} from "@chakra-ui/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { DriftAlert } from "@/components/DriftAlert";
import { StatusBadge } from "@/components/StatusBadge";
import { TrafficToggle } from "@/components/TrafficToggle";
import { useAuthGate } from "@/hooks/useAuthGate";
import { syncDisplayForCard } from "@/lib/syncDisplay";
import { toastMutation } from "@/lib/toastMutation";
import {
  getErrorMessage,
  useDisableCompanyMutation,
  useEnableCompanyMutation,
  useFetchCompanyMutation,
  useGetCompanyQuery,
  useGetCompanyStatsQuery,
  usePatchGeoMutation,
} from "@/store/api";

export default function CompanyCardPage() {
  const { ready, authed } = useAuthGate();
  const params = useParams<{ id: string }>();
  const companyId = Number(params.id);
  const [geoInput, setGeoInput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const companyQuery = useGetCompanyQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const statsQuery = useGetCompanyStatsQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const [enableCompany, enableState] = useEnableCompanyMutation();
  const [disableCompany, disableState] = useDisableCompanyMutation();
  const [patchGeo, geoState] = usePatchGeoMutation();
  const [fetchCompany, fetchState] = useFetchCompanyMutation();

  const company = companyQuery.data;
  const offersStream = company?.streams.find((s) => s.type === "offers");
  const offerNames =
    offersStream?.offers.filter((o) => !o.removed) ?? [];
  const sync = offersStream?.sync ?? company?.sync ?? null;
  const fetchDisabled =
    sync === "update_mode" ||
    !company ||
    company.lifecycle !== "ready" ||
    company.drift?.campaign_missing === true;

  if (!ready || !authed) return null;

  async function onTraffic(next: "active" | "disabled") {
    if (!company) return;
    setError(null);
    try {
      if (next === "active") {
        await toastMutation(
          enableCompany({
            companyId: company.id,
            expected_version: company.version,
          }).unwrap(),
          {
            loading: "Enabling traffic…",
            success: "Company updated",
            errorTitle: "Update failed",
          },
        );
      } else {
        await toastMutation(
          disableCompany({
            companyId: company.id,
            expected_version: company.version,
          }).unwrap(),
          {
            loading: "Disabling traffic…",
            success: "Company updated",
            errorTitle: "Update failed",
          },
        );
      }
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function onSaveGeo() {
    if (!company || geoInput === null) return;
    setError(null);
    setMessage(null);
    const geo_codes = geoInput
      .split(",")
      .map((g) => g.trim().toUpperCase())
      .filter(Boolean);
    try {
      await toastMutation(
        patchGeo({
          companyId: company.id,
          geo_codes,
          expected_version: company.version,
        }).unwrap(),
        {
          loading: "Saving geo…",
          success: "Company updated",
          errorTitle: "Update failed",
        },
      );
      setGeoInput(null);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function onFetch() {
    if (fetchDisabled || !company) return;
    setError(null);
    setMessage(null);
    try {
      await toastMutation(fetchCompany(company.id).unwrap(), {
        loading: "Fetching from tracker…",
        success: "Fetched from tracker",
        errorTitle: "Fetch failed",
      });
      setMessage("Fetched from tracker.");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const syncUi = company
    ? syncDisplayForCard(company.sync, company.drift)
    : null;

  return (
    <AppShell
      title={company ? company.name : "Company"}
      breadcrumbs={
        company
          ? [
              { label: "Companies", href: "/companies" },
              { label: company.name },
            ]
          : [{ label: "Companies", href: "/companies" }, { label: "Company" }]
      }
    >
      <Stack gap="4">
        {companyQuery.isError ? (
          <Text color="fg.error">{getErrorMessage(companyQuery.error)}</Text>
        ) : null}
        {error ? (
          <Text color="fg.error" fontSize="sm">
            {error}
          </Text>
        ) : null}
        {message ? (
          <Text color="fg.muted" fontSize="sm">
            {message}
          </Text>
        ) : null}

        {company ? (
          <>
            <Stack gap="2">
              <Heading textStyle="pageTitle" color="gray.fg">
                {company.name}
              </Heading>
              <Text color="fg.muted" textStyle="muted">
                version {company.version} · {company.lifecycle}
              </Text>
              <HStack gap="2" flexWrap="wrap">
                <StatusBadge
                  label={company.traffic_status}
                  tone={company.traffic_status === "active" ? "green" : "red"}
                />
                {syncUi ? (
                  <StatusBadge label={syncUi.label} tone={syncUi.tone} />
                ) : null}
                {company.geo_codes.map((g, i) => (
                  <StatusBadge
                    key={g}
                    label={g}
                    tone={
                      i === 0 ? "blue" : i === 1 ? "cyan" : "purple"
                    }
                  />
                ))}
              </HStack>
            </Stack>

            <DriftAlert
              drift={company.drift}
              reconcileUnavailable={company.reconcile_unavailable}
            />

            <HStack gap="2" flexWrap="wrap">
              <Button
                size="sm"
                variant="outline"
                colorPalette="cyan"
                loading={fetchState.isLoading}
                disabled={fetchDisabled}
                opacity={fetchDisabled ? 0.4 : 1}
                title={
                  fetchDisabled
                    ? "Fetch requires synced flow (not updating) and an existing campaign"
                    : "Pull campaign state from Keitaro"
                }
                onClick={() => void onFetch()}
              >
                Fetch
              </Button>
              <Button
                asChild
                size="sm"
                variant="solid"
                colorPalette="blue"
                disabled={company.lifecycle !== "ready"}
              >
                <Link href={`/companies/${company.id}/streams`}>
                  View details
                </Link>
              </Button>
            </HStack>

            <SimpleGrid columns={{ base: 1, md: 3 }} gap="3">
              {(
                [
                  ["Clicks", statsQuery.data?.clicks],
                  ["Uniques", statsQuery.data?.uniques],
                  ["Bots", statsQuery.data?.bots],
                ] as const
              ).map(([label, value]) => (
                <Box
                  key={label}
                  bg="bg"
                  borderWidth="1px"
                  borderColor="border.subtle"
                  rounded="md"
                  p="4"
                >
                  <Text fontSize="xs" fontWeight="medium" color="fg.muted">
                    {label}
                  </Text>
                  <Text
                    fontSize="2xl"
                    fontWeight="semibold"
                    color="gray.fg"
                    mt="2"
                  >
                    {value == null
                      ? "—"
                      : value.toLocaleString("en-US").replace(/,/g, " ")}
                  </Text>
                </Box>
              ))}
            </SimpleGrid>

            <TrafficToggle
              status={company.traffic_status}
              disabled={company.lifecycle !== "ready"}
              loading={enableState.isLoading || disableState.isLoading}
              onToggle={(next) => void onTraffic(next)}
            />

            <Box
              bg="bg"
              borderWidth="1px"
              borderColor="border.subtle"
              rounded="md"
              p="4"
            >
              <Field.Root>
                <Field.Label>Geo codes</Field.Label>
                <HStack>
                  <Input
                    value={geoInput ?? company.geo_codes.join(", ")}
                    onChange={(e) => setGeoInput(e.target.value)}
                    aria-label="Geo codes"
                  />
                  <Button
                    size="sm"
                    variant="outline"
                    colorPalette="cyan"
                    loading={geoState.isLoading}
                    onClick={() => void onSaveGeo()}
                  >
                    Save geo
                  </Button>
                </HStack>
              </Field.Root>
            </Box>

            <Stack gap="2">
              <Heading as="h2" textStyle="sm.medium" color="gray.fg">
                Streams
              </Heading>
              <Box
                bg="bg"
                borderWidth="1px"
                borderColor="border.subtle"
                rounded="md"
                overflow="hidden"
              >
                {offerNames.map((o) => (
                  <Box
                    key={o.offer_id}
                    px="4"
                    py="3"
                    borderBottomWidth="1px"
                    borderColor="border.subtle"
                  >
                    <Text fontSize="sm" fontWeight="medium" color="gray.fg">
                      {o.name ?? `Offer ${o.offer_id}`}
                    </Text>
                  </Box>
                ))}
                {offerNames.length === 0 ? (
                  <Box px="4" py="3">
                    <Text color="fg.muted" fontSize="sm">
                      No active offers
                    </Text>
                  </Box>
                ) : null}
              </Box>
            </Stack>
          </>
        ) : companyQuery.isLoading ? (
          <Text color="fg.muted">Loading…</Text>
        ) : null}
      </Stack>
    </AppShell>
  );
}
