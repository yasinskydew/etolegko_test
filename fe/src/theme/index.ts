import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

const config = defineConfig({
  theme: {
    tokens: {
      fonts: {
        heading: { value: "var(--font-heading), Georgia, serif" },
        body: { value: "var(--font-body), system-ui, sans-serif" },
      },
    },
    semanticTokens: {
      colors: {
        // Rely on Chakra defaults: bg.subtle, bg, gray.fg, fg.muted, border.subtle,
        // blue.fg / cyan.fg via colorPalette. Keep brand accent explicit for shell.
        brand: {
          fg: { value: { _light: "{colors.blue.600}", _dark: "{colors.blue.300}" } },
        },
      },
    },
  },
  globalCss: {
    body: {
      bg: "bg.subtle",
      color: "gray.fg",
    },
  },
});

export const system = createSystem(defaultConfig, config);
