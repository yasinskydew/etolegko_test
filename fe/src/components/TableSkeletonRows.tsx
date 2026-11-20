"use client";

import { Skeleton, Table } from "@chakra-ui/react";

export type SkeletonColumn = {
  /** Skeleton bar width inside the cell. */
  width?: string;
  /** Matches the tallest real content of the cell (text, input, button). */
  height?: string;
};

type Props = {
  columns: number | SkeletonColumn[];
  rows?: number;
};

const WIDTHS = ["70%", "50%", "40%", "60%"];

export function TableSkeletonRows({ columns, rows = 5 }: Props) {
  const cols: SkeletonColumn[] =
    typeof columns === "number"
      ? Array.from({ length: columns }, () => ({}))
      : columns;

  return (
    <>
      {Array.from({ length: rows }, (_, r) => (
        <Table.Row key={r} aria-hidden>
          {cols.map((col, c) => (
            <Table.Cell key={c}>
              <Skeleton
                h={col.height ?? "5"}
                w={col.width ?? WIDTHS[(r + c) % WIDTHS.length]}
                rounded="sm"
              />
            </Table.Cell>
          ))}
        </Table.Row>
      ))}
    </>
  );
}
