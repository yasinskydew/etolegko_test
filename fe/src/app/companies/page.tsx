"use client";

import {
  Box,
  Button,
  Heading,
  HStack,
  Input,
  SimpleGrid,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { CreateCompanyModal } from "@/components/CreateCompanyModal";
import { PagePagination } from "@/components/PagePagination";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuthGate } from "@/hooks/useAuthGate";
import { syncDisplayForList } from "@/lib/syncDisplay";
import { getErrorMessage, useListCompaniesQuery } from "@/store/api";

const PAGE_SIZE = 20;

const LEGEND = [
  { label: "active", tone: "green" as const },
  { label: "disabled", tone: "red" as const },
  { label: "creating", tone: "purple" as const },
  { label: "synced", tone: "green" as const },
  { label: "update mode", tone: "orange" as const },
];

export default function CompaniesPage() {
  const { ready, authed } = useAuthGate();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);

  const { data, isFetching, error } = useListCompaniesQuery(
    { q: search || undefined, page, page_size: PAGE_SIZE },
    { skip: !authed },
  );

  const total = data?.total ?? 0;
  const items = data?.items ?? [];

  if (!ready || !authed) return null;

  function applySearch() {
    setPage(1);
    setSearch(q.trim());
  }

  return (
    <AppShell title="Companies">
      <Stack gap="4">
        <HStack justify="space-between" align="start" flexWrap="wrap" gap="3">
          <Stack gap="1">
            <Heading textStyle="pageTitle" color="gray.fg">
              Companies
            </Heading>
            <Text color="fg.muted" textStyle="muted">
              Only companies stored in this app
            </Text>
          </Stack>
          <Button
            size="sm"
            variant="solid"
            colorPalette="blue"
            onClick={() => setCreateOpen(true)}
          >
            Create
          </Button>
        </HStack>

        <Input
          maxW={{ base: "full", md: "360px" }}
          placeholder="Company name"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") applySearch();
          }}
          onBlur={applySearch}
          aria-label="Search companies"
        />

        {error ? (
          <Text color="fg.error" fontSize="sm">
            {getErrorMessage(error)}
          </Text>
        ) : null}

        <Box display={{ base: "none", md: "block" }}>
          <Table.Root size="sm" variant="outline" bg="bg" rounded="md">
            <Table.Header>
              <Table.Row bg="bg.subtle">
                <Table.ColumnHeader>Name</Table.ColumnHeader>
                <Table.ColumnHeader>Geo</Table.ColumnHeader>
                <Table.ColumnHeader>Traffic</Table.ColumnHeader>
                <Table.ColumnHeader>Lifecycle</Table.ColumnHeader>
                <Table.ColumnHeader>Sync</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {items.map((c) => {
                const syncUi = syncDisplayForList(c.sync);
                const geos = c.geo_codes ?? [];
                const geo = geos.length > 0 ? geos.join(", ") : null;
                return (
                  <Table.Row key={c.id}>
                    <Table.Cell>
                      <Link href={`/companies/${c.id}`}>{c.name}</Link>
                    </Table.Cell>
                    <Table.Cell>
                      {geo ? (
                        geo
                      ) : (
                        <Text color="fg.muted">—</Text>
                      )}
                    </Table.Cell>
                    <Table.Cell>
                      {c.lifecycle === "creating" ? "—" : c.traffic_status}
                    </Table.Cell>
                    <Table.Cell>{c.lifecycle}</Table.Cell>
                    <Table.Cell>
                      {syncUi ? syncUi.label : "—"}
                    </Table.Cell>
                  </Table.Row>
                );
              })}
              {!isFetching && items.length === 0 ? (
                <Table.Row>
                  <Table.Cell colSpan={5}>
                    <Text color="fg.muted">No companies yet.</Text>
                  </Table.Cell>
                </Table.Row>
              ) : null}
            </Table.Body>
          </Table.Root>
        </Box>

        <SimpleGrid
          display={{ base: "grid", md: "none" }}
          columns={1}
          gap="4"
        >
          {items.map((c) => {
            const syncUi = syncDisplayForList(c.sync);
            const geos = c.geo_codes ?? [];
            const geo = geos.length > 0 ? geos.join(", ") : "—";
            return (
              <Box
                key={c.id}
                bg="bg"
                borderWidth="1px"
                borderColor="border.subtle"
                rounded="md"
                p="4"
                as="article"
              >
                <Link href={`/companies/${c.id}`}>
                  <Stack gap="2">
                    <Text fontWeight="medium" color="gray.fg">
                      {c.name}
                    </Text>
                    <StatusBadge
                      label={
                        c.lifecycle === "creating"
                          ? "creating"
                          : c.traffic_status
                      }
                      tone={
                        c.lifecycle === "creating"
                          ? "purple"
                          : c.traffic_status === "active"
                            ? "green"
                            : "red"
                      }
                    />
                    {syncUi ? (
                      <StatusBadge
                        label={syncUi.label}
                        tone={syncUi.tone}
                      />
                    ) : null}
                    <Text fontSize="xs" color="fg.muted">
                      {geo}
                    </Text>
                  </Stack>
                </Link>
              </Box>
            );
          })}
          {!isFetching && items.length === 0 ? (
            <Text color="fg.muted">No companies yet.</Text>
          ) : null}
        </SimpleGrid>

        <HStack gap="2" flexWrap="wrap">
          {LEGEND.map((item) => (
            <StatusBadge key={item.label} label={item.label} tone={item.tone} />
          ))}
        </HStack>

        <PagePagination
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
        />
      </Stack>

      <CreateCompanyModal
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(id) => router.push(`/companies/${id}`)}
      />
    </AppShell>
  );
}
