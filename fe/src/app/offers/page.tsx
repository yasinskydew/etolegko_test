"use client";

import {
  Heading,
  HStack,
  Input,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { useAuthGate } from "@/hooks/useAuthGate";
import { getErrorMessage, useListOffersQuery } from "@/store/api";

export default function OffersPage() {
  const { ready, authed } = useAuthGate();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const { data, isFetching, error } = useListOffersQuery(
    { q: search || undefined },
    { skip: !authed },
  );

  if (!ready || !authed) return null;

  return (
    <AppShell title="Offers">
      <Stack gap="6">
        <Stack gap="1">
          <Heading size="xl" color="blue.fg" fontFamily="heading">
            Offers
          </Heading>
          <Text color="fg.muted" fontSize="sm">
            Read-only catalog from the tracker
          </Text>
        </Stack>

        <HStack maxW="md">
          <Input
            placeholder="Search offers"
            value={q}
            aria-label="Search offers"
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setSearch(q.trim());
            }}
          />
        </HStack>

        {error ? (
          <Text color="fg.error">{getErrorMessage(error)}</Text>
        ) : null}

        <Table.Root size="sm" variant="outline" bg="bg">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>ID</Table.ColumnHeader>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {(data?.items ?? []).map((o) => (
              <Table.Row key={o.offer_id}>
                <Table.Cell>{o.offer_id}</Table.Cell>
                <Table.Cell>{o.name ?? "—"}</Table.Cell>
              </Table.Row>
            ))}
            {!isFetching && (data?.items?.length ?? 0) === 0 ? (
              <Table.Row>
                <Table.Cell colSpan={2}>
                  <Text color="fg.muted">No offers</Text>
                </Table.Cell>
              </Table.Row>
            ) : null}
          </Table.Body>
        </Table.Root>
      </Stack>
    </AppShell>
  );
}
