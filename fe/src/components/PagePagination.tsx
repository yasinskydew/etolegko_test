"use client";

import { ButtonGroup, IconButton, Pagination } from "@chakra-ui/react";

type Props = {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
};

export function PagePagination({ page, pageSize, total, onPageChange }: Props) {
  if (total <= pageSize) return null;

  return (
    <Pagination.Root
      count={total}
      pageSize={pageSize}
      page={page}
      onPageChange={(d) => onPageChange(d.page)}
    >
      <ButtonGroup variant="outline" size="sm" gap="2">
        <Pagination.PrevTrigger asChild>
          <IconButton aria-label="Previous page" variant="ghost">
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
          <IconButton aria-label="Next page" variant="ghost">
            ›
          </IconButton>
        </Pagination.NextTrigger>
      </ButtonGroup>
    </Pagination.Root>
  );
}
