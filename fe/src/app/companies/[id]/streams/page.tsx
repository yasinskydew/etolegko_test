"use client";

import {
  Box,
  Button,
  Heading,
  HStack,
  IconButton,
  Image,
  Input,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { DriftAlert } from "@/components/DriftAlert";
import { OfferCombobox } from "@/components/OfferCombobox";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuthGate } from "@/hooks/useAuthGate";
import {
  clearQueue,
  enqueueAction,
  getTabId,
  isQueueDirty,
  readQueue,
  removeQueued,
  type QueueAction,
} from "@/lib/actionQueue";
import { canPinOrSetPercent, displayPercent } from "@/lib/streamRules";
import type { OfferCatalogItem, OfferRow } from "@/lib/types";
import {
  getErrorMessage,
  useCancelCompanyMutation,
  useFetchCompanyMutation,
  useGetCompanyQuery,
  usePushCompanyMutation,
  useStreamActionMutation,
} from "@/store/api";

export default function StreamsEditorPage() {
  const { ready, authed } = useAuthGate();
  const params = useParams<{ id: string }>();
  const companyId = Number(params.id);
  const [tabId, setTabId] = useState("ssr");
  const [queueVersion, setQueueVersion] = useState(0);
  const [selectedOffer, setSelectedOffer] = useState<OfferCatalogItem | null>(
    null,
  );
  const [percentDraft, setPercentDraft] = useState<Record<number, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const companyQuery = useGetCompanyQuery(companyId, {
    skip: !authed || !Number.isFinite(companyId),
  });
  const [streamAction, actionState] = useStreamActionMutation();
  const [pushCompany, pushState] = usePushCompanyMutation();
  const [cancelCompany, cancelState] = useCancelCompanyMutation();
  const [fetchCompany, fetchState] = useFetchCompanyMutation();

  useEffect(() => {
    setTabId(getTabId());
  }, []);

  const company = companyQuery.data;
  const offersStream = company?.streams.find((s) => s.type === "offers");
  const googleStream = company?.streams.find((s) => s.type === "google");
  const plainStreams =
    company?.streams.filter((s) => s.type === "plain") ?? [];
  const offers = offersStream?.offers ?? [];
  const sync = offersStream?.sync ?? company?.sync ?? null;

  const dirty = useMemo(() => {
    if (!Number.isFinite(companyId) || tabId === "ssr") return false;
    return isQueueDirty(companyId, tabId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, tabId, queueVersion, company?.version]);

  const queueItems = useMemo(() => {
    if (!Number.isFinite(companyId) || tabId === "ssr") return [];
    return readQueue(companyId, tabId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, tabId, queueVersion]);

  const fetchDisabled =
    sync === "update_mode" ||
    dirty ||
    !company ||
    company.lifecycle !== "ready" ||
    company.drift?.campaign_missing === true;

  const bumpQueue = useCallback(() => setQueueVersion((v) => v + 1), []);

  async function runAction(action: QueueAction) {
    if (!company || !offersStream) return;
    setError(null);
    setMessage(null);

    if (action.action === "pin" || action.action === "set_percent") {
      const check = canPinOrSetPercent(
        offers,
        action.offer_id,
        action.action === "set_percent" ? action.percent : undefined,
      );
      if (!check.ok) {
        setError(check.reason);
        return;
      }
    }

    const queued = enqueueAction(companyId, tabId, action);
    bumpQueue();

    try {
      await streamAction({
        companyId,
        streamId: offersStream.id,
        action: action.action,
        offer_id: action.offer_id,
        percent: "percent" in action ? action.percent : undefined,
        expected_version: company.version,
      }).unwrap();
      removeQueued(companyId, tabId, [queued.id]);
      bumpQueue();
      setMessage("Share updated from server response.");
    } catch (err) {
      const status =
        err && typeof err === "object" && "status" in err
          ? (err as { status?: number }).status
          : undefined;
      if (status === 422) {
        removeQueued(companyId, tabId, [queued.id]);
        bumpQueue();
      }
      setError(getErrorMessage(err));
      void companyQuery.refetch();
    }
  }

  async function flushQueueThenPush() {
    if (!company || !offersStream) return;
    setError(null);
    setMessage(null);
    try {
      let version = company.version;
      const pending = readQueue(companyId, tabId);
      for (const item of pending) {
        await streamAction({
          companyId,
          streamId: offersStream.id,
          action: item.action,
          offer_id: item.offer_id,
          percent: "percent" in item ? item.percent : undefined,
          expected_version: version,
        }).unwrap();
        removeQueued(companyId, tabId, [item.id]);
        bumpQueue();
        const refreshed = await companyQuery.refetch().unwrap();
        version = refreshed.version;
      }
      await pushCompany(companyId).unwrap();
      clearQueue(companyId, tabId);
      bumpQueue();
      setMessage("Pushed to tracker.");
    } catch (err) {
      setError(getErrorMessage(err));
      void companyQuery.refetch();
    }
  }

  async function onCancel() {
    if (!company) return;
    setError(null);
    try {
      clearQueue(companyId, tabId);
      bumpQueue();
      await cancelCompany(companyId).unwrap();
      setMessage("Cancelled. Working copy restored from snapshot.");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  async function onFetch() {
    if (fetchDisabled) return;
    setError(null);
    try {
      await fetchCompany(companyId).unwrap();
      setMessage("Fetched from tracker.");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  function shareHint(offer: OfferRow): string {
    if (offer.removed) return "removed";
    if (offer.pinned) return "pinned";
    return "free";
  }

  function renderOfferRow(offer: OfferRow) {
    const draft = percentDraft[offer.offer_id] ?? String(displayPercent(offer));
    return (
      <Table.Row
        key={offer.offer_id}
        bg={offer.removed ? "bg.subtle" : "bg"}
      >
        <Table.Cell>
          <Text fontSize="sm" fontWeight="medium" color="gray.fg">
            {offer.offer_id} {offer.name ?? ""}
          </Text>
        </Table.Cell>
        <Table.Cell>
          {offer.removed ? (
            <Stack gap="0">
              <Text fontSize="sm">0%</Text>
              <Text fontSize="xs" color="fg.muted">
                removed
              </Text>
            </Stack>
          ) : (
            <Stack gap="0">
              <HStack>
                <Input
                  size="sm"
                  maxW="16"
                  value={draft}
                  aria-label={`Share for ${offer.offer_id}`}
                  onChange={(e) =>
                    setPercentDraft((prev) => ({
                      ...prev,
                      [offer.offer_id]: e.target.value,
                    }))
                  }
                  onBlur={() => {
                    const n = Number(draft);
                    if (
                      !Number.isInteger(n) ||
                      n < 1 ||
                      n > 100 ||
                      n === offer.percent
                    ) {
                      setPercentDraft((prev) => {
                        const next = { ...prev };
                        delete next[offer.offer_id];
                        return next;
                      });
                      return;
                    }
                    void runAction({
                      action: "set_percent",
                      offer_id: offer.offer_id,
                      percent: n,
                    });
                  }}
                />
                <Text fontSize="sm">%</Text>
              </HStack>
              <Text fontSize="xs" color="fg.muted">
                {shareHint(offer)}
              </Text>
            </Stack>
          )}
        </Table.Cell>
        <Table.Cell>
          <Text color="fg.muted">—</Text>
        </Table.Cell>
        <Table.Cell>
          <Text color="fg.muted">—</Text>
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
                  void runAction({
                    action: "restore",
                    offer_id: offer.offer_id,
                  })
                }
              >
                <Image src="/icons/undo.svg" alt="" boxSize="4" />
              </IconButton>
            ) : (
              <>
                <IconButton
                  size="sm"
                  variant="outline"
                  colorPalette="blue"
                  aria-label={offer.pinned ? "Unpin" : "Pin"}
                  onClick={() =>
                    void runAction({
                      action: offer.pinned ? "unpin" : "pin",
                      offer_id: offer.offer_id,
                    })
                  }
                >
                  <Image
                    src={offer.pinned ? "/icons/pin-off.svg" : "/icons/pin.svg"}
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
                    void runAction({
                      action: "remove",
                      offer_id: offer.offer_id,
                    })
                  }
                >
                  <Image src="/icons/trash-2.svg" alt="" boxSize="4" />
                </IconButton>
              </>
            )}
          </HStack>
        </Table.Cell>
      </Table.Row>
    );
  }

  if (!ready || !authed) return null;

  const totalActive = offers
    .filter((o) => !o.removed)
    .reduce((s, o) => s + o.percent, 0);

  return (
    <AppShell title="Companies / Streams">
      <Stack gap="4">
        <Heading
          fontSize="2xl"
          fontWeight="semibold"
          color="gray.fg"
          fontFamily="heading"
        >
          Streams
        </Heading>

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
              <Heading as="h2" fontSize="md" fontWeight="semibold" mb="2">
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
                <Heading as="h2" fontSize="md" fontWeight="semibold">
                  Plain #{s.position}
                </Heading>
                <Text color="fg.muted" fontSize="sm">
                  No offers
                </Text>
              </Box>
            ))}

            <Box
              bg="bg"
              borderWidth="1px"
              borderColor="border.subtle"
              rounded="md"
              p="4"
            >
              <HStack justify="space-between" mb="2" flexWrap="wrap" gap="2">
                <Heading as="h2" fontSize="md" fontWeight="semibold">
                  Offers
                </Heading>
                {sync ? (
                  <StatusBadge
                    label={sync === "update_mode" ? "update mode" : "synced"}
                    tone={sync === "update_mode" ? "orange" : "green"}
                  />
                ) : null}
              </HStack>
              <Text color="fg.muted" fontSize="sm" mb="3">
                Unpublished. Push sends active offers. Removed offers stay in
                the archive. Fetch waits for Push or Cancel.
                {dirty ? " Local queue has pending actions." : ""}
              </Text>

              <Box overflowX="auto">
                <Table.Root size="sm" variant="outline">
                  <Table.Header>
                    <Table.Row>
                      <Table.ColumnHeader color="fg.muted" fontSize="xs">
                        Offer
                      </Table.ColumnHeader>
                      <Table.ColumnHeader color="fg.muted" fontSize="xs">
                        Share
                      </Table.ColumnHeader>
                      <Table.ColumnHeader color="fg.muted" fontSize="xs">
                        Stats
                      </Table.ColumnHeader>
                      <Table.ColumnHeader color="fg.muted" fontSize="xs">
                        Trends
                      </Table.ColumnHeader>
                      <Table.ColumnHeader
                        color="fg.muted"
                        fontSize="xs"
                        w="20"
                      >
                        Actions
                      </Table.ColumnHeader>
                    </Table.Row>
                  </Table.Header>
                  <Table.Body>{offers.map(renderOfferRow)}</Table.Body>
                </Table.Root>
              </Box>

              <Text mt="3" fontSize="sm" fontWeight="medium" color="gray.fg">
                Total {totalActive}
                {queueItems.length ? ` · queue ${queueItems.length}` : ""}
              </Text>

              <HStack mt="4" align="center" flexWrap="wrap" gap="2">
                <Box flex="1" minW="200px">
                  <OfferCombobox
                    value={selectedOffer}
                    onChange={setSelectedOffer}
                    label=""
                  />
                </Box>
                <Button
                  size="sm"
                  variant="solid"
                  colorPalette="blue"
                  disabled={!selectedOffer || actionState.isLoading}
                  onClick={() => {
                    if (!selectedOffer) return;
                    void runAction({
                      action: "add",
                      offer_id: selectedOffer.offer_id,
                    }).then(() => setSelectedOffer(null));
                  }}
                >
                  Add
                </Button>
              </HStack>

              <HStack mt="4" gap="2" flexWrap="wrap">
                <Button
                  size="sm"
                  variant="solid"
                  colorPalette="blue"
                  loading={pushState.isLoading}
                  disabled={
                    company.drift?.campaign_missing === true ||
                    (sync !== "update_mode" && !dirty)
                  }
                  onClick={() => void flushQueueThenPush()}
                >
                  Push
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  colorPalette="cyan"
                  loading={cancelState.isLoading}
                  disabled={sync !== "update_mode" && !dirty}
                  onClick={() => void onCancel()}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  colorPalette="cyan"
                  loading={fetchState.isLoading}
                  disabled={fetchDisabled}
                  opacity={fetchDisabled ? 0.4 : 1}
                  title={
                    fetchDisabled
                      ? "Fetch requires synced flow and empty local queue"
                      : undefined
                  }
                  onClick={() => void onFetch()}
                >
                  Fetch
                </Button>
              </HStack>
            </Box>
          </>
        ) : companyQuery.isLoading ? (
          <Text color="fg.muted">Loading…</Text>
        ) : null}
      </Stack>
    </AppShell>
  );
}
