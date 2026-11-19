"use client";

import {
  Button,
  Dialog,
  Field,
  Input,
  Portal,
  Stack,
  Text,
} from "@chakra-ui/react";
import { useState } from "react";

import { getErrorCode, getErrorMessage, useCreateCompanyMutation } from "@/store/api";
import type { OfferCatalogItem } from "@/lib/types";

import { OfferCombobox } from "./OfferCombobox";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated?: (companyId: number) => void;
};

const NAME_RE = /^[a-zA-Z0-9_\- ]{1,64}$/;

export function CreateCompanyModal({ open, onOpenChange, onCreated }: Props) {
  const [name, setName] = useState("");
  const [geos, setGeos] = useState("MX, AU, RO");
  const [offer, setOffer] = useState<OfferCatalogItem | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [createCompany, { isLoading }] = useCreateCompanyMutation();

  function reset() {
    setName("");
    setGeos("MX, AU, RO");
    setOffer(null);
    setLocalError(null);
    setNameError(null);
  }

  async function onSubmit() {
    setLocalError(null);
    setNameError(null);
    const trimmed = name.trim();
    if (!NAME_RE.test(trimmed) || trimmed !== name.trim()) {
      setNameError("Name: 1–64 chars, letters, digits, _ - space; no edge spaces.");
      return;
    }
    const geo_codes = geos
      .split(",")
      .map((g) => g.trim().toUpperCase())
      .filter(Boolean);
    if (geo_codes.length === 0) {
      setLocalError("Add at least one geo code.");
      return;
    }
    if (!offer) {
      setLocalError("Pick an offer.");
      return;
    }

    try {
      const company = await createCompany({
        name: trimmed,
        geo_codes,
        offer_id: offer.offer_id,
        idempotencyKey: crypto.randomUUID(),
      }).unwrap();
      reset();
      onOpenChange(false);
      onCreated?.(company.id);
    } catch (err) {
      const code = getErrorCode(err);
      const msg = getErrorMessage(err);
      if (code === "name_taken") {
        setNameError(msg || "This name is already used.");
      } else {
        setLocalError(msg);
      }
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(d) => {
        if (!d.open) reset();
        onOpenChange(d.open);
      }}
      placement="center"
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content bg="bg" rounded="xl" maxW="480px" p="6" gap="4">
            <Dialog.Header p="0" mb="0">
              <Dialog.Title textStyle="cardTitle" color="gray.fg">
                New company
              </Dialog.Title>
            </Dialog.Header>
            <Dialog.Body p="0">
              <Text color="fg.muted" mb="4" textStyle="sm.medium">
                One offer, 100%. Domain, group and source are set by the server.
              </Text>
              <Stack gap="4">
                <Field.Root invalid={!!nameError}>
                  <Field.Label fontWeight="semibold">Name</Field.Label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Company name"
                  />
                  {nameError ? <Field.ErrorText>{nameError}</Field.ErrorText> : null}
                </Field.Root>
                <Field.Root>
                  <Field.Label fontWeight="semibold">Geo</Field.Label>
                  <Input
                    value={geos}
                    onChange={(e) => setGeos(e.target.value)}
                    placeholder="MX, AU, RO"
                  />
                </Field.Root>
                <OfferCombobox value={offer} onChange={setOffer} label="Offer" />
                {localError ? (
                  <Text color="fg.error" fontSize="sm">
                    {localError}
                  </Text>
                ) : null}
              </Stack>
            </Dialog.Body>
            <Dialog.Footer p="0" mt="2" gap="2" justifyContent="flex-end">
              <Dialog.ActionTrigger asChild>
                <Button size="sm" variant="outline" colorPalette="cyan">
                  Cancel
                </Button>
              </Dialog.ActionTrigger>
              <Button
                size="sm"
                variant="solid"
                colorPalette="blue"
                loading={isLoading}
                onClick={() => void onSubmit()}
              >
                Create
              </Button>
            </Dialog.Footer>
            <Dialog.CloseTrigger />
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
