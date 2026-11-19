"use client";

import { Alert } from "@chakra-ui/react";

import type { Drift } from "@/lib/types";

type Props = {
  drift: Drift | null;
  reconcileUnavailable?: boolean;
};

function driftParts(drift: Drift): string[] {
  const parts: string[] = [];
  if (drift.campaign_missing) parts.push("campaign missing");
  if (drift.offers) parts.push("offers");
  if (drift.geo) parts.push("geo");
  if (drift.traffic) parts.push("traffic");
  if (drift.streams) parts.push("streams");
  return parts;
}

export function DriftAlert({ drift, reconcileUnavailable }: Props) {
  if (reconcileUnavailable) {
    return (
      <Alert.Root status="warning">
        <Alert.Indicator />
        <Alert.Content>
          <Alert.Title>Tracker unavailable</Alert.Title>
          <Alert.Description>
            Showing database state. Reconcile could not run.
          </Alert.Description>
        </Alert.Content>
      </Alert.Root>
    );
  }

  if (!drift) return null;
  const parts = driftParts(drift);
  if (parts.length === 0) return null;

  return (
    <Alert.Root status="warning" rounded="md">
      <Alert.Content>
        <Alert.Title fontWeight="medium">
          Tracker data differs
          {parts.length ? ` (${parts.join(", ")})` : ""}
        </Alert.Title>
      </Alert.Content>
    </Alert.Root>
  );
}
