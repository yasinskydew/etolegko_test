"use client";

import {
  Combobox,
  Portal,
  createListCollection,
  useFilter,
  useListCollection,
} from "@chakra-ui/react";
import { useEffect, useMemo, useState } from "react";

import { useLazyListOffersQuery } from "@/store/api";
import type { OfferCatalogItem } from "@/lib/types";

type Props = {
  label?: string;
  value: OfferCatalogItem | null;
  onChange: (offer: OfferCatalogItem | null) => void;
  disabled?: boolean;
};

export function OfferCombobox({
  label = "Offer",
  value,
  onChange,
  disabled,
}: Props) {
  const [query, setQuery] = useState("");
  const [trigger, result] = useLazyListOffersQuery();
  const { contains } = useFilter({ sensitivity: "base" });

  useEffect(() => {
    const t = setTimeout(() => {
      void trigger({ q: query || undefined });
    }, 200);
    return () => clearTimeout(t);
  }, [query, trigger]);

  const items = useMemo(
    () => result.data?.items ?? [],
    [result.data?.items],
  );

  const { collection, filter, set } = useListCollection({
    initialItems: items,
    filter: contains,
    itemToString: (item) => item.name ?? String(item.offer_id),
    itemToValue: (item) => String(item.offer_id),
  });

  useEffect(() => {
    set(items);
  }, [items, set]);

  const selectedCollection = useMemo(
    () =>
      createListCollection({
        items: value ? [value] : [],
        itemToString: (item: OfferCatalogItem) =>
          item.name ?? String(item.offer_id),
        itemToValue: (item: OfferCatalogItem) => String(item.offer_id),
      }),
    [value],
  );

  return (
    <Combobox.Root
      collection={collection}
      disabled={disabled}
      openOnClick
      onInputValueChange={(details) => {
        setQuery(details.inputValue);
        filter(details.inputValue);
      }}
      onValueChange={(details) => {
        const id = details.value[0];
        if (!id) {
          onChange(null);
          return;
        }
        const found =
          items.find((i) => String(i.offer_id) === id) ??
          selectedCollection.items.find((i) => String(i.offer_id) === id) ??
          null;
        onChange(found);
      }}
      value={value ? [String(value.offer_id)] : []}
      width="full"
    >
      <Combobox.Label>{label}</Combobox.Label>
      <Combobox.Control>
        <Combobox.Input placeholder="Search offers" />
        <Combobox.IndicatorGroup>
          <Combobox.ClearTrigger />
          <Combobox.Trigger />
        </Combobox.IndicatorGroup>
      </Combobox.Control>
      <Portal>
        <Combobox.Positioner>
          <Combobox.Content>
            <Combobox.Empty>No offers found</Combobox.Empty>
            {collection.items.map((item) => (
              <Combobox.Item item={item} key={item.offer_id}>
                <Combobox.ItemText>
                  {item.name ?? `Offer ${item.offer_id}`}
                </Combobox.ItemText>
                <Combobox.ItemIndicator />
              </Combobox.Item>
            ))}
          </Combobox.Content>
        </Combobox.Positioner>
      </Portal>
    </Combobox.Root>
  );
}
