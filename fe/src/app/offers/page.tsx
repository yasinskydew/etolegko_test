"use client";

import {
  Heading,
  Input,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PagePagination } from "@/components/PagePagination";
import { useAuthGate } from "@/hooks/useAuthGate";
import { getErrorMessage, useListOffersQuery } from "@/store/api";

const PAGE_SIZE = 20;

export default function OffersPage() {
  const { ready, authed } = useAuthGate();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const { data, isFetching, error } = useListOffersQuery(
    { q: search || undefined },
    { skip: !authed },
  );

  const items = data?.items ?? [];
  const paged = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return items.slice(start, start + PAGE_SIZE);
  }, [items, page]);

  if (!ready || !authed) return null;

  function applySearch() {
    setPage(1);
    setSearch(q.trim());
  }

  return (
    <AppShell title="Offers">
      <Stack gap="4">
        <Stack gap="1">
          <Heading
            size="xl"
            fontWeight="semibold"
            color="gray.fg"
            fontFamily="heading"
          >
            Offers
          </Heading>
          <Text color="fg.muted" fontSize="sm">
            Read-only catalog from Keitaro
          </Text>
        </Stack>

        <Input
          maxW={{ base: "full", md: "360px" }}
          placeholder="Search offers"
          value={q}
          aria-label="Search offers"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") applySearch();
          }}
          onBlur={applySearch}
        />

        {error ? (
          <Text color="fg.error">{getErrorMessage(error)}</Text>
        ) : null}

        <Table.Root size="sm" variant="outline" bg="bg" rounded="md">
          <Table.Header>
            <Table.Row bg="bg.subtle">
              <Table.ColumnHeader>ID</Table.ColumnHeader>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
              <Table.ColumnHeader>Country</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {paged.map((o) => (
              <Table.Row key={o.offer_id}>
                <Table.Cell>{o.offer_id}</Table.Cell>
                <Table.Cell>{o.name ?? "—"}</Table.Cell>
                <Table.Cell>
                  <Text color="fg.muted">—</Text>
                </Table.Cell>
              </Table.Row>
            ))}
            {!isFetching && items.length === 0 ? (
              <Table.Row>
                <Table.Cell colSpan={3}>
                  <Text color="fg.muted">No offers</Text>
                </Table.Cell>
              </Table.Row>
            ) : null}
          </Table.Body>
        </Table.Root>

        <PagePagination
          page={page}
          pageSize={PAGE_SIZE}
          total={items.length}
          onPageChange={setPage}
        />
      </Stack>
    </AppShell>
  );
}
