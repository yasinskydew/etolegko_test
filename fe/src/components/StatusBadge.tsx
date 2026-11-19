"use client";

import { Badge } from "@chakra-ui/react";

type Props = {
  label: string;
  tone?: "blue" | "cyan" | "gray" | "green" | "orange" | "red";
};

export function StatusBadge({ label, tone = "gray" }: Props) {
  return (
    <Badge size="sm" colorPalette={tone} variant="subtle">
      {label}
    </Badge>
  );
}
