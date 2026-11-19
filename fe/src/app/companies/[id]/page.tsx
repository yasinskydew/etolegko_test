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
  Table,
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
import {
  getErrorMessage,
  useDisableCompanyMutation,
  useEnableCompanyMutation,
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

  const companyQuery = useGetCompanyQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const statsQuery = useGetCompanyStatsQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const [enableCompany, enableState] = useEnableCompanyMutation();
  const [disableCompany, disableState] = useDisableCompanyMutation();
  const [patchGeo, geoState] = usePatchGeoMutation();

  const company = companyQuery.data;
  const offersStream = company?.streams.find((s) => s.type === "offers");
  const offerNames =
    offersStream?.offers.filter((o) => !o.removed) ?? [];

  if (!ready || !authed) return null;

  async function onTraffic(next: "active" | "disabled") {
    if (!company) return;
    setError(null);
    try {
      if (next === "active") {
        await enableCompany({
          companyId: company.id,
          expected_version: company.version,
        }).unwrap();
      } else {
        await disableCompany({
          companyId: company.id,
          expected_version: company.version,
        }).unwrap();
      }
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function onSaveGeo() {
    if (!company || geoInput === null) return;
    setError(null);
    const geo_codes = geoInput
      .split(",")
      .map((g) => g.trim().toUpperCase())
      .filter(Boolean);
    try {
      await patchGeo({
        companyId: company.id,
        geo_codes,
        expected_version: company.version,
      }).unwrap();
      setGeoInput(null);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <AppShell title={company ? `Companies / ${company.name}` : "Company"}>
      <Stack gap="6">
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
              <Heading size="xl" color="blue.fg" fontFamily="heading">
                {company.name}
              </Heading>
              <Text color="fg.muted" fontSize="sm">
                version {company.version} · {company.lifecycle}
              </Text>
              <HStack gap="2" flexWrap="wrap">
                <StatusBadge
                  label={company.lifecycle}
                  tone={company.lifecycle === "ready" ? "green" : "orange"}
                />
                <StatusBadge
                  label={company.traffic_status}
                  tone={company.traffic_status === "active" ? "green" : "gray"}
                />
                {company.sync ? (
                  <StatusBadge
                    label={
                      company.sync === "update_mode" ? "update mode" : "synced"
                    }
                    tone={company.sync === "update_mode" ? "orange" : "cyan"}
                  />
                ) : null}
                {company.geo_codes.map((g) => (
                  <StatusBadge key={g} label={g} tone="blue" />
                ))}
              </HStack>
            </Stack>

            <DriftAlert
              drift={company.drift}
              reconcileUnavailable={company.reconcile_unavailable}
            />

            <SimpleGrid columns={{ base: 1, md: 3 }} gap="4">
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
                  <Text fontSize="sm" color="fg.muted">
                    {label}
                  </Text>
                  <Text fontSize="2xl" fontWeight="semibold" color="gray.fg">
                    {value == null ? "—" : value.toLocaleString()}
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
                    value={geoInput ?? company.geo_codes.join(",")}
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

            <Stack gap="3">
              <Heading as="h2" size="md">
                Streams
              </Heading>
              <Table.Root size="sm" variant="outline" bg="bg">
                <Table.Body>
                  {offerNames.map((o) => (
                    <Table.Row key={o.offer_id}>
                      <Table.Cell>
                        {o.name ?? `Offer ${o.offer_id}`}
                      </Table.Cell>
                    </Table.Row>
                  ))}
                  {offerNames.length === 0 ? (
                    <Table.Row>
                      <Table.Cell>
                        <Text color="fg.muted">No active offers</Text>
                      </Table.Cell>
                    </Table.Row>
                  ) : null}
                </Table.Body>
              </Table.Root>
              <HStack justify="flex-end">
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
            </Stack>
          </>
        ) : companyQuery.isLoading ? (
          <Text color="fg.muted">Loading…</Text>
        ) : null}
      </Stack>
    </AppShell>
  );
}
