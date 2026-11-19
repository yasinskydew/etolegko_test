"use client";

import { HStack, Switch, Text } from "@chakra-ui/react";

import type { TrafficStatus } from "@/lib/types";

type Props = {
  status: TrafficStatus;
  disabled?: boolean;
  loading?: boolean;
  onToggle: (next: TrafficStatus) => void;
};

export function TrafficToggle({ status, disabled, loading, onToggle }: Props) {
  const active = status === "active";
  return (
    <HStack gap="3">
      <Text fontSize="sm" color="gray.fg">
        {active ? "Active" : "Disabled"}
      </Text>
      <Switch.Root
        checked={active}
        disabled={disabled || loading}
        colorPalette="blue"
        onCheckedChange={(details) =>
          onToggle(details.checked ? "active" : "disabled")
        }
      >
        <Switch.HiddenInput aria-label="Traffic status" />
        <Switch.Control>
          <Switch.Thumb />
        </Switch.Control>
      </Switch.Root>
    </HStack>
  );
}
