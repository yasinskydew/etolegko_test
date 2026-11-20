"use client";

import {
  Box,
  Button,
  Heading,
  HStack,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { DriftAlert } from "@/components/DriftAlert";
import { StatusBadge } from "@/components/StatusBadge";
import { TableSkeletonRows } from "@/components/TableSkeletonRows";
import { TrafficToggle } from "@/components/TrafficToggle";
import { useAuthGate } from "@/hooks/useAuthGate";
import { readCompanyDraft } from "@/lib/companyDraft";
import { displayPercent } from "@/lib/streamRules";
import { syncDisplayForCard } from "@/lib/syncDisplay";
import { toastMutation } from "@/lib/toastMutation";
import {
  getErrorMessage,
  useDisableCompanyMutation,
  useEnableCompanyMutation,
  useFetchCompanyMutation,
  useGetCompanyQuery,
  useGetCompanyStatsQuery,
} from "@/store/api";

export default function CompanyCardPage() {
  const { ready, authed } = useAuthGate();
  const params = useParams<{ id: string }>();
  const companyId = Number(params.id);
  const [error, setError] = useState<string | null>(null);

  const companyQuery = useGetCompanyQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const statsQuery = useGetCompanyStatsQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const [enableCompany, enableState] = useEnableCompanyMutation();
  const [disableCompany, disableState] = useDisableCompanyMutation();
  const [fetchCompany, fetchState] = useFetchCompanyMutation();

  const company = companyQuery.data;
  const offersStream = company?.streams.find((s) => s.type === "offers");
  const googleStream = company?.streams.find((s) => s.type === "google");
  const plainStreams =
    company?.streams.filter((s) => s.type === "plain") ?? [];
  const offers = offersStream?.offers ?? [];

  const draftDirty = useMemo(() => {
    if (!Number.isFinite(companyId)) return false;
    return readCompanyDraft(companyId) != null;
  }, [companyId, company?.id, companyQuery.fulfilledTimeStamp]);

  const fetchDisabled =
    draftDirty ||
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
          enableCompany({ companyId: company.id }).unwrap(),
          {
            loading: "Enabling traffic…",
            success: "Company updated",
            errorTitle: "Update failed",
          },
        );
      } else {
        await toastMutation(
          disableCompany({ companyId: company.id }).unwrap(),
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

  async function onFetch() {
    if (fetchDisabled || !company) return;
    setError(null);
    try {
      await toastMutation(fetchCompany(company.id).unwrap(), {
        loading: "Fetching from tracker…",
        success: "Fetched from tracker",
        errorTitle: "Fetch failed",
      });
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  const syncUi = company
    ? syncDisplayForCard(company.lifecycle, company.drift, draftDirty)
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

        {company ? (
          <>
            <Stack gap="2">
              <Heading textStyle="pageTitle" color="gray.fg">
                {company.name}
              </Heading>
              <Text color="fg.muted" textStyle="muted">
                {company.lifecycle}
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
                    tone={i === 0 ? "blue" : i === 1 ? "cyan" : "purple"}
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
                    ? "Fetch requires no local draft and an existing campaign"
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
                <Link href={`/companies/${company.id}/edit`}>Edit</Link>
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
                  {statsQuery.isLoading ? (
                    <Skeleton h="8" w="20" mt="2" />
                  ) : (
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
                  )}
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
              <Text fontSize="sm" fontWeight="medium" color="gray.fg" mb="1">
                Geo
              </Text>
              <Text fontSize="sm" color="fg.muted">
                {company.geo_codes.join(", ") || "—"}
              </Text>
            </Box>

            <Box
              bg="bg"
              borderWidth="1px"
              borderColor="border.subtle"
              rounded="md"
              p="4"
            >
              <Heading as="h2" textStyle="md.semibold" mb="2">
                Google
              </Heading>
              <Text color="fg.muted" fontSize="sm">
                {googleStream
                  ? company.geo_codes.length
                    ? `${company.geo_codes.join(", ")} · no offers`
                    : "No offers"
                  : "No google stream"}
              </Text>
            </Box>

            {plainStreams.map((s) => (
              <Box
                key={s.id}
                bg="bg"
                borderWidth="1px"
                borderColor="border.subtle"
                rounded="md"
                p="4"
              >
                <Heading as="h2" textStyle="md.semibold">
                  Plain #{s.position}
                </Heading>
              </Box>
            ))}

            <Box
              bg={draftDirty ? "yellow.subtle" : "bg"}
              borderWidth="1px"
              borderColor="border.subtle"
              rounded="md"
              p="4"
            >
              <HStack justify="space-between" mb="2">
                <Heading as="h2" textStyle="md.semibold">
                  Offers
                </Heading>
                {draftDirty ? (
                  <StatusBadge label="updating" tone="orange" />
                ) : null}
              </HStack>
              <Table.Root size="sm" variant="outline">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Offer</Table.ColumnHeader>
                    <Table.ColumnHeader>Share</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {offers.map((o) => (
                    <Table.Row key={o.offer_id}>
                      <Table.Cell>
                        {o.offer_id} {o.name ?? ""}
                        {o.removed ? " (removed)" : ""}
                      </Table.Cell>
                      <Table.Cell>{displayPercent(o)}%</Table.Cell>
                    </Table.Row>
                  ))}
                  {offers.length === 0 ? (
                    <Table.Row>
                      <Table.Cell colSpan={2}>
                        <Text color="fg.muted">No offers</Text>
                      </Table.Cell>
                    </Table.Row>
                  ) : null}
                </Table.Body>
              </Table.Root>
            </Box>
          </>
        ) : companyQuery.isLoading ? (
          <Stack gap="4" aria-busy aria-label="Loading company">
            <Stack gap="2">
              <Skeleton h="8" w="48" />
              <Skeleton h="5" w="20" />
              <HStack gap="2">
                <Skeleton h="5" w="16" rounded="full" />
                <Skeleton h="5" w="12" rounded="full" />
              </HStack>
            </Stack>
            <SimpleGrid columns={{ base: 1, md: 3 }} gap="3">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} h="24" rounded="md" />
              ))}
            </SimpleGrid>
            <Box
              bg="bg"
              borderWidth="1px"
              borderColor="border.subtle"
              rounded="md"
              p="4"
            >
              <Heading as="h2" textStyle="md.semibold" mb="2">
                Offers
              </Heading>
              <Table.Root size="sm" variant="outline">
                <Table.Header>
                  <Table.Row>
                    <Table.ColumnHeader>Offer</Table.ColumnHeader>
                    <Table.ColumnHeader>Share</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  <TableSkeletonRows columns={[{}, { width: "12" }]} />
                </Table.Body>
              </Table.Root>
            </Box>
          </Stack>
        ) : null}
      </Stack>
    </AppShell>
  );
}
