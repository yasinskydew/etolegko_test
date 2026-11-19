import { createSystem, defaultConfig } from "@chakra-ui/react";

export const system = createSystem(defaultConfig, {
  theme: {
    tokens: {
      fonts: {
        heading: { value: "var(--font-heading), system-ui, sans-serif" },
        body: { value: "var(--font-body), system-ui, sans-serif" },
      },
    },
  },
});
