"use client";

import { Alert } from "@chakra-ui/react";

import type { Drift } from "@/lib/types";

type Props = {
  drift: Drift | null;
  reconcileUnavailable?: boolean;
};

function hasDrift(drift: Drift): boolean {
  return (
    drift.campaign_missing ||
    drift.offers ||
    drift.geo ||
    drift.traffic ||
    drift.streams
  );
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

  if (!drift || !hasDrift(drift)) return null;

  return (
    <Alert.Root status="warning" rounded="md">
      <Alert.Content>
        <Alert.Title fontWeight="medium">Tracker data differs</Alert.Title>
      </Alert.Content>
    </Alert.Root>
  );
}
