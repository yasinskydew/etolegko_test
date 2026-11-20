"use client";

import { ChakraProvider } from "@chakra-ui/react";
import { ThemeProvider } from "next-themes";
import type { ReactNode } from "react";

import { Toaster } from "@/components/ui/toaster";
import { system } from "@/theme";

import { StoreProvider } from "./StoreProvider";

export function Provider({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      storageKey="chakra-ui-color-mode"
      disableTransitionOnChange
    >
      <ChakraProvider value={system}>
        <StoreProvider>
          {children}
          <Toaster />
        </StoreProvider>
      </ChakraProvider>
    </ThemeProvider>
  );
}
