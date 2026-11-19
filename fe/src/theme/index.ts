import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

import { textStyles, typographyTokens } from "./foundations/typography";

const config = defineConfig({
  theme: {
    tokens: {
      ...typographyTokens,
    },
    textStyles,
    semanticTokens: {
      colors: {
        // Rely on Chakra defaults: bg.subtle, bg, gray.fg, fg.muted, border.subtle,
        // blue.fg / cyan.fg via colorPalette.
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
      fontFamily: "body",
      textStyle: "sm",
    },
  },
});

export const system = createSystem(defaultConfig, config);
