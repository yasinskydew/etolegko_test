"use client";

import {
  Badge,
  Button,
  HStack,
  Heading,
  Input,
  Stack,
  Table,
  Text,
} from "@chakra-ui/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { CreateCompanyModal } from "@/components/CreateCompanyModal";
import { PagePagination } from "@/components/PagePagination";
import { StatusBadge } from "@/components/StatusBadge";
import { useAuthGate } from "@/hooks/useAuthGate";
import {
  getErrorMessage,
  useDisableCompanyMutation,
  useEnableCompanyMutation,
  useListCompaniesQuery,
} from "@/store/api";

const PAGE_SIZE = 20;

export default function CompaniesPage() {
  const { ready, authed } = useAuthGate();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isFetching, error, refetch } = useListCompaniesQuery(
    { q: search || undefined, page, page_size: PAGE_SIZE },
    { skip: !authed },
  );
  const [enableCompany, enableState] = useEnableCompanyMutation();
  const [disableCompany, disableState] = useDisableCompanyMutation();

  const total = data?.total ?? 0;
  const items = data?.items ?? [];

  const busy = enableState.isLoading || disableState.isLoading;

  const subtitle = useMemo(
    () => "Only companies stored in this app",
    [],
  );

  if (!ready || !authed) return null;

  async function setTraffic(
    id: number,
    version: number,
    next: "active" | "disabled",
  ) {
    setActionError(null);
    try {
      if (next === "active") {
        await enableCompany({ companyId: id, expected_version: version }).unwrap();
      } else {
        await disableCompany({
          companyId: id,
          expected_version: version,
        }).unwrap();
      }
    } catch (err) {
      setActionError(getErrorMessage(err));
      void refetch();
    }
  }

  return (
    <AppShell title="Companies">
      <Stack gap="6">
        <HStack justify="space-between" align="start" flexWrap="wrap" gap="3">
          <Stack gap="1">
            <Heading size="xl" color="blue.fg" fontFamily="heading">
              Companies
            </Heading>
            <Text color="fg.muted" fontSize="sm">
              {subtitle}
            </Text>
          </Stack>
          <Button
            size="sm"
            variant="solid"
            colorPalette="blue"
            onClick={() => setCreateOpen(true)}
          >
            New
          </Button>
        </HStack>

        <HStack maxW="md" gap="2">
          <Input
            placeholder="Search by name"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setPage(1);
                setSearch(q.trim());
              }
            }}
            aria-label="Search companies"
          />
          <Button
            size="sm"
            variant="outline"
            colorPalette="cyan"
            onClick={() => {
              setPage(1);
              setSearch(q.trim());
            }}
          >
            Search
          </Button>
        </HStack>

        {actionError ? (
          <Text color="fg.error" fontSize="sm">
            {actionError}
          </Text>
        ) : null}
        {error ? (
          <Text color="fg.error" fontSize="sm">
            {getErrorMessage(error)}
          </Text>
        ) : null}

        <Table.Root size="sm" variant="outline" bg="bg">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader>Name</Table.ColumnHeader>
              <Table.ColumnHeader>Lifecycle</Table.ColumnHeader>
              <Table.ColumnHeader>Traffic</Table.ColumnHeader>
              <Table.ColumnHeader>Sync</Table.ColumnHeader>
              <Table.ColumnHeader>Actions</Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {items.map((c) => (
              <Table.Row key={c.id}>
                <Table.Cell>
                  <Link href={`/companies/${c.id}`}>{c.name}</Link>
                </Table.Cell>
                <Table.Cell>
                  <StatusBadge
                    label={c.lifecycle}
                    tone={c.lifecycle === "ready" ? "green" : "orange"}
                  />
                </Table.Cell>
                <Table.Cell>
                  <Badge
                    size="sm"
                    colorPalette={
                      c.traffic_status === "active" ? "green" : "gray"
                    }
                  >
                    {c.traffic_status}
                  </Badge>
                </Table.Cell>
                <Table.Cell>
                  {c.sync ? (
                    <StatusBadge
                      label={c.sync === "update_mode" ? "update mode" : "synced"}
                      tone={c.sync === "update_mode" ? "orange" : "cyan"}
                    />
                  ) : (
                    <Text color="fg.muted">—</Text>
                  )}
                </Table.Cell>
                <Table.Cell>
                  <HStack gap="2">
                    {c.traffic_status === "active" ? (
                      <Button
                        size="sm"
                        variant="outline"
                        colorPalette="cyan"
                        disabled={busy || c.lifecycle !== "ready"}
                        onClick={() =>
                          void setTraffic(c.id, c.version, "disabled")
                        }
                      >
                        Disable
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="solid"
                        colorPalette="blue"
                        disabled={busy || c.lifecycle !== "ready"}
                        onClick={() =>
                          void setTraffic(c.id, c.version, "active")
                        }
                      >
                        Enable
                      </Button>
                    )}
                  </HStack>
                </Table.Cell>
              </Table.Row>
            ))}
            {!isFetching && items.length === 0 ? (
              <Table.Row>
                <Table.Cell colSpan={5}>
                  <Text color="fg.muted">No companies yet.</Text>
                </Table.Cell>
              </Table.Row>
            ) : null}
          </Table.Body>
        </Table.Root>

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
