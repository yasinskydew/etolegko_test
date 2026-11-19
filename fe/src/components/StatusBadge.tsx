"use client";

import { Status } from "@chakra-ui/react";

type Props = {
  label: string;
  tone?: "blue" | "cyan" | "gray" | "green" | "orange" | "purple" | "red";
};

export function StatusBadge({ label, tone = "gray" }: Props) {
  return (
    <Status.Root size="sm" colorPalette={tone}>
      <Status.Indicator />
      {label}
    </Status.Root>
  );
}
