"use client";

import {
  Box,
  Button,
  Field,
  Heading,
  HStack,
  IconButton,
  Image,
  Input,
  Skeleton,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { DriftAlert } from "@/components/DriftAlert";
import { OfferCombobox } from "@/components/OfferCombobox";
import { StatusBadge } from "@/components/StatusBadge";
import { TableSkeletonRows } from "@/components/TableSkeletonRows";
import { toaster } from "@/components/ui/toaster";
import { useAuthGate } from "@/hooks/useAuthGate";
import {
  clearCompanyDraft,
  draftsEqual,
  readCompanyDraft,
  writeCompanyDraft,
  type CompanyDraft,
} from "@/lib/companyDraft";
import { canPinOrSetPercent, displayPercent } from "@/lib/streamRules";
import { syncDisplayForCard } from "@/lib/syncDisplay";
import { toastMutation } from "@/lib/toastMutation";
import type { OfferCatalogItem, OfferRow } from "@/lib/types";
import {
  applyAdd,
  applyPin,
  applyRemove,
  applyRestore,
  applySetPercent,
  applyUnpin,
  WeightError,
} from "@/lib/weightUtil";
import {
  getErrorMessage,
  useApplyCompanyMutation,
  useFetchCompanyMutation,
  useGetCompanyQuery,
} from "@/store/api";

function serverDraft(company: {
  geo_codes: string[];
  streams: { type: string; offers: OfferRow[] }[];
}): CompanyDraft {
  const offers =
    company.streams.find((s) => s.type === "offers")?.offers ?? [];
  return {
    geo_codes: [...company.geo_codes],
    offers: offers.map((o) => ({ ...o })),
  };
}

export default function CompanyEditPage() {
  const { ready, authed } = useAuthGate();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const companyId = Number(params.id);

  const [draft, setDraft] = useState<CompanyDraft | null>(null);
  const [geoInput, setGeoInput] = useState("");
  const [selectedOffer, setSelectedOffer] = useState<OfferCatalogItem | null>(
    null,
  );
  const [percentDraft, setPercentDraft] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);

  const companyQuery = useGetCompanyQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const [applyCompany, applyState] = useApplyCompanyMutation();
  const [fetchCompany, fetchState] = useFetchCompanyMutation();

  const company = companyQuery.data;

  useEffect(() => {
    if (!company) return;
    const stored = readCompanyDraft(company.id);
    const base = serverDraft(company);
    if (stored) {
      setDraft(stored);
      setGeoInput(stored.geo_codes.join(", "));
    } else {
      setDraft(base);
      setGeoInput(base.geo_codes.join(", "));
    }
  }, [company?.id, companyQuery.fulfilledTimeStamp]);

  const baseline = useMemo(
    () => (company ? serverDraft(company) : null),
    [company],
  );
  const dirty =
    !!draft && !!baseline && !draftsEqual(draft, baseline);

  useEffect(() => {
    if (!company || !draft) return;
    if (dirty) writeCompanyDraft(company.id, draft);
    else clearCompanyDraft(company.id);
  }, [company, draft, dirty]);

  const offers = draft?.offers ?? [];
  const googleStream = company?.streams.find((s) => s.type === "google");
  const plainStreams =
    company?.streams.filter((s) => s.type === "plain") ?? [];

  const syncUi = company
    ? syncDisplayForCard(company.sync, company.drift, dirty)
    : null;

  if (!ready || !authed) return null;

  function persistDraft(next: CompanyDraft) {
    setDraft(next);
    setError(null);
  }

  function parseGeo(raw: string): string[] {
    return raw
      .split(",")
      .map((g) => g.trim().toUpperCase())
      .filter(Boolean);
  }

  function onGeoBlur() {
    if (!draft) return;
    persistDraft({ ...draft, geo_codes: parseGeo(geoInput) });
  }

  function runLocal(
    mutator: (offers: OfferRow[]) => OfferRow[],
  ) {
    if (!draft) return;
    try {
      persistDraft({ ...draft, offers: mutator(draft.offers) });
    } catch (err) {
      const msg =
        err instanceof WeightError ? err.message : "Invalid offer change";
      setError(msg);
      toaster.error({
        title: "Invalid share",
        description: msg,
        meta: { closable: true },
      });
    }
  }

  async function onPush() {
    if (!company || !draft) return;
    setError(null);
    const geo_codes = parseGeo(geoInput);
    try {
      await toastMutation(
        applyCompany({
          companyId: company.id,
          geo_codes,
          offers: draft.offers.map((o) => ({
            offer_id: o.offer_id,
            percent: o.percent,
            pinned: o.pinned,
            removed: o.removed,
            position: o.position,
          })),
        }).unwrap(),
        {
          loading: "Pushing to tracker…",
          success: "Pushed to tracker",
          errorTitle: "Push failed",
        },
      );
      clearCompanyDraft(company.id);
      setDraft(null);
      await companyQuery.refetch();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function onCancel() {
    if (!company || !baseline) return;
    clearCompanyDraft(company.id);
    setDraft(baseline);
    setGeoInput(baseline.geo_codes.join(", "));
    setError(null);
    toaster.success({ title: "Draft discarded" });
    router.push(`/companies/${company.id}`);
  }

  async function onFetch() {
    if (!company || dirty) return;
    setError(null);
    try {
      await toastMutation(fetchCompany(company.id).unwrap(), {
        loading: "Fetching from tracker…",
        success: "Fetched from tracker",
        errorTitle: "Fetch failed",
      });
      clearCompanyDraft(company.id);
      setDraft(null);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <AppShell
      title={company ? `Edit ${company.name}` : "Edit"}
      breadcrumbs={
        company
          ? [
              { label: "Companies", href: "/companies" },
              { label: company.name, href: `/companies/${company.id}` },
              { label: "Edit" },
            ]
          : [
              { label: "Companies", href: "/companies" },
              { label: "Edit" },
            ]
      }
    >
      <Stack gap="4">
        {companyQuery.isError ? (
          <Text color="fg.error">{getErrorMessage(companyQuery.error)}</Text>
        ) : null}
        <Box minH="2.75rem" aria-live="polite">
          {error ? (
            <Text color="fg.error" fontSize="sm" lineClamp={2}>
              {error}
            </Text>
          ) : (
            <Text fontSize="sm" visibility="hidden" aria-hidden>
              &nbsp;
            </Text>
          )}
        </Box>

        {company && draft ? (
          <>
            <HStack justify="space-between" flexWrap="wrap" gap="2">
              <Stack gap="1">
                <Heading textStyle="pageTitle" color="gray.fg">
                  {company.name}
                </Heading>
                <HStack gap="2">
                  {syncUi ? (
                    <StatusBadge label={syncUi.label} tone={syncUi.tone} />
                  ) : null}
                </HStack>
              </Stack>
              <HStack gap="2">
                <Button
                  size="sm"
                  variant="solid"
                  colorPalette="blue"
                  loading={applyState.isLoading}
                  disabled={!dirty}
                  onClick={() => void onPush()}
                >
                  Push to KT
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  colorPalette="cyan"
                  disabled={!dirty}
                  onClick={() => void onCancel()}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  colorPalette="cyan"
                  loading={fetchState.isLoading}
                  disabled={dirty || company.drift?.campaign_missing === true}
                  onClick={() => void onFetch()}
                >
                  Fetch
                </Button>
              </HStack>
            </HStack>

            <DriftAlert
              drift={company.drift}
              reconcileUnavailable={company.reconcile_unavailable}
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
                <Input
                  value={geoInput}
                  onChange={(e) => setGeoInput(e.target.value)}
                  onBlur={onGeoBlur}
                  aria-label="Geo codes"
                />
              </Field.Root>
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
                  ? `${parseGeo(geoInput).join(", ") || "—"} · no offers`
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
              bg={dirty ? "yellow.subtle" : "bg"}
              borderWidth="1px"
              borderColor="border.subtle"
              rounded="md"
              p="4"
            >
              <HStack justify="space-between" mb="2">
                <Heading as="h2" textStyle="md.semibold">
                  Offers
                </Heading>
                {dirty ? (
                  <StatusBadge label="updating" tone="orange" />
                ) : null}
              </HStack>
              <Text color="fg.muted" fontSize="sm" mb="3">
                Push sends active offers. Removed offers stay in the archive.
                Fetch waits for Push or Cancel.
              </Text>

              <Box overflowX="auto">
                <Table.Root size="sm" variant="outline">
                  <Table.Header>
                    <Table.Row>
                      <Table.ColumnHeader>Offer</Table.ColumnHeader>
                      <Table.ColumnHeader>Share</Table.ColumnHeader>
                      <Table.ColumnHeader w="20">Actions</Table.ColumnHeader>
                    </Table.Row>
                  </Table.Header>
                  <Table.Body>
                    {offers.map((offer) => {
                      const draftPct =
                        percentDraft[offer.offer_id] ??
                        String(displayPercent(offer));
                      return (
                        <Table.Row
                          key={offer.offer_id}
                          bg={offer.removed ? "bg.subtle" : undefined}
                        >
                          <Table.Cell>
                            {offer.offer_id} {offer.name ?? ""}
                          </Table.Cell>
                          <Table.Cell>
                            {offer.removed ? (
                              <Text fontSize="sm">0%</Text>
                            ) : (
                              <HStack>
                                <Input
                                  size="sm"
                                  maxW="16"
                                  value={draftPct}
                                  disabled={offer.pinned}
                                  aria-label={`Share for ${offer.offer_id}`}
                                  onChange={(e) =>
                                    setPercentDraft((prev) => ({
                                      ...prev,
                                      [offer.offer_id]: e.target.value,
                                    }))
                                  }
                                  onBlur={() => {
                                    const n = Number(draftPct);
                                    const reset = () =>
                                      setPercentDraft((prev) => {
                                        const next = { ...prev };
                                        delete next[offer.offer_id];
                                        return next;
                                      });
                                    if (
                                      !Number.isInteger(n) ||
                                      n < 1 ||
                                      n > 100
                                    ) {
                                      reset();
                                      setError(
                                        "Share must be an integer from 1 to 100.",
                                      );
                                      return;
                                    }
                                    if (n === offer.percent) {
                                      reset();
                                      return;
                                    }
                                    const check = canPinOrSetPercent(
                                      offers,
                                      offer.offer_id,
                                      n,
                                    );
                                    if (!check.ok) {
                                      reset();
                                      setError(check.reason);
                                      return;
                                    }
                                    runLocal((rows) =>
                                      applySetPercent(rows, offer.offer_id, n),
                                    );
                                    reset();
                                  }}
                                />
                                <Text fontSize="sm">%</Text>
                              </HStack>
                            )}
                          </Table.Cell>
                          <Table.Cell>
                            <HStack gap="2" justify="center">
                              {offer.removed ? (
                                <IconButton
                                  size="sm"
                                  variant="outline"
                                  colorPalette="cyan"
                                  aria-label="Bring back"
                                  onClick={() =>
                                    runLocal((rows) =>
                                      applyRestore(rows, offer.offer_id),
                                    )
                                  }
                                >
                                  <Image
                                    src="/icons/undo.svg"
                                    alt=""
                                    boxSize="4"
                                  />
                                </IconButton>
                              ) : (
                                <>
                                  <IconButton
                                    size="sm"
                                    variant="outline"
                                    colorPalette="blue"
                                    aria-label={
                                      offer.pinned ? "Unpin" : "Pin"
                                    }
                                    onClick={() =>
                                      runLocal((rows) =>
                                        offer.pinned
                                          ? applyUnpin(rows, offer.offer_id)
                                          : applyPin(rows, offer.offer_id),
                                      )
                                    }
                                  >
                                    <Image
                                      src={
                                        offer.pinned
                                          ? "/icons/pin-off.svg"
                                          : "/icons/pin.svg"
                                      }
                                      alt=""
                                      boxSize="4"
                                    />
                                  </IconButton>
                                  <IconButton
                                    size="sm"
                                    variant="outline"
                                    colorPalette="red"
                                    aria-label="Remove"
                                    onClick={() =>
                                      runLocal((rows) =>
                                        applyRemove(rows, offer.offer_id),
                                      )
                                    }
                                  >
                                    <Image
                                      src="/icons/trash-2.svg"
                                      alt=""
                                      boxSize="4"
                                    />
                                  </IconButton>
                                </>
                              )}
                            </HStack>
                          </Table.Cell>
                        </Table.Row>
                      );
                    })}
                  </Table.Body>
                </Table.Root>
              </Box>

              <HStack mt="4" align="center" flexWrap="wrap" gap="2">
                <Box flex="1" minW="200px">
                  <OfferCombobox
                    value={selectedOffer}
                    onChange={setSelectedOffer}
                    label=""
                    excludeOfferIds={offers.map((o) => o.offer_id)}
                  />
                </Box>
                <Button
                  size="sm"
                  variant="solid"
                  colorPalette="blue"
                  disabled={!selectedOffer}
                  onClick={() => {
                    if (!selectedOffer) return;
                    const offer = selectedOffer;
                    runLocal((rows) => {
                      const next = applyAdd(rows, offer.offer_id);
                      return next.map((r) =>
                        r.offer_id === offer.offer_id
                          ? { ...r, name: offer.name }
                          : r,
                      );
                    });
                    setSelectedOffer(null);
                  }}
                >
                  Add
                </Button>
              </HStack>
            </Box>
          </>
        ) : companyQuery.isLoading || (company && !draft) ? (
          <Stack gap="4" aria-busy aria-label="Loading company">
            <HStack justify="space-between" flexWrap="wrap" gap="2">
              <Stack gap="1">
                <Skeleton h="8" w="48" />
                <Skeleton h="5" w="16" rounded="full" />
              </Stack>
              <HStack gap="2">
                <Skeleton h="8" w="24" />
                <Skeleton h="8" w="20" />
                <Skeleton h="8" w="16" />
              </HStack>
            </HStack>
            <Skeleton h="24" rounded="md" />
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
              <Box overflowX="auto">
                <Table.Root size="sm" variant="outline">
                  <Table.Header>
                    <Table.Row>
                      <Table.ColumnHeader>Offer</Table.ColumnHeader>
                      <Table.ColumnHeader>Share</Table.ColumnHeader>
                      <Table.ColumnHeader w="20">Actions</Table.ColumnHeader>
                    </Table.Row>
                  </Table.Header>
                  <Table.Body>
                    <TableSkeletonRows
                      columns={[
                        {},
                        { width: "20", height: "8" },
                        { width: "20", height: "8" },
                      ]}
                    />
                  </Table.Body>
                </Table.Root>
              </Box>
            </Box>
          </Stack>
        ) : null}
      </Stack>
    </AppShell>
  );
}
