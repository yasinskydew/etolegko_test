"use client";

import { ButtonGroup, IconButton, Pagination } from "@chakra-ui/react";

type Props = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function PagePagination({ page, pageSize, total, onPageChange }: Props) {
  const count = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;

  return (
    <Pagination.Root
      count={total}
      pageSize={pageSize}
      page={page}
      onPageChange={(d) => onPageChange(d.page)}
    >
      <ButtonGroup variant="outline" size="sm">
        <Pagination.PrevTrigger asChild>
          <IconButton aria-label="Previous page" colorPalette="cyan">
            ‹
          </IconButton>
        </Pagination.PrevTrigger>
        <Pagination.Items
          render={(item) => (
            <IconButton
              aria-label={`Page ${item.value}`}
              variant={item.value === page ? "solid" : "outline"}
              colorPalette={item.value === page ? "blue" : "cyan"}
            >
              {item.value}
            </IconButton>
          )}
        />
        <Pagination.NextTrigger asChild>
          <IconButton aria-label="Next page" colorPalette="cyan">
            ›
          </IconButton>
        </Pagination.NextTrigger>
      </ButtonGroup>
      <Pagination.PageText format="long" ml="3" fontSize="sm" color="fg.muted" />
      {/* count kept for a11y when single page edge cases */}
      <span hidden>{count}</span>
    </Pagination.Root>
  );
}
