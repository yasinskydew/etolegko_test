"use client";

import { Alert } from "@chakra-ui/react";

import { driftActive } from "@/lib/syncDisplay";
import type { Drift } from "@/lib/types";

type Props = {
  drift: Drift | null;
  reconcileUnavailable?: boolean;
};

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

  if (!driftActive(drift)) return null;

  return (
    <Alert.Root status="warning" rounded="md">
      <Alert.Content>
        <Alert.Title fontWeight="medium">Tracker data differs</Alert.Title>
      </Alert.Content>
    </Alert.Root>
  );
}
