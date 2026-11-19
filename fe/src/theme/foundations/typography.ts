/**
 * Typography tokens aligned with Figma etolegko_design (fonts/body = Inter).
 * Sizes/weights from variable defs + Desktop screens (login/companies/streams).
 */
export const typographyTokens = {
  fonts: {
    heading: { value: "var(--font-inter), Inter, system-ui, sans-serif" },
    body: { value: "var(--font-inter), Inter, system-ui, sans-serif" },
  },
  fontSizes: {
    xs: { value: "12px" }, // fontSizes/xs
    sm: { value: "14px" }, // fontSizes/sm
    md: { value: "16px" }, // brand subtitle / body
    lg: { value: "18px" },
    xl: { value: "20px" }, // card titles (Sign in, Create company)
    "2xl": { value: "24px" },
    "3xl": { value: "28px" }, // brand wordmark / page H1 in shell
  },
  fontWeights: {
    normal: { value: "400" }, // fontWeights/normal
    medium: { value: "500" }, // fontWeights/medium
    semibold: { value: "600" }, // titles in Desktop frames
    bold: { value: "700" },
  },
  lineHeights: {
    shorter: { value: "16px" }, // xs text (badges, table captions)
    short: { value: "20px" }, // sm text / buttons
    moderate: { value: "24px" },
    tall: { value: "28px" },
    normal: { value: "normal" },
  },
} as const;

/**
 * Named text styles from Figma composites (xs/font-normal, sm/font-medium, …)
 * plus screen roles (brand, pageTitle, sectionTitle).
 */
export const textStyles = {
  "xs": {
    value: {
      fontFamily: "body",
      fontSize: "xs",
      fontWeight: "normal",
      lineHeight: "shorter",
      letterSpacing: "0",
    },
  },
  "xs.medium": {
    value: {
      fontFamily: "body",
      fontSize: "xs",
      fontWeight: "medium",
      lineHeight: "shorter",
      letterSpacing: "0",
    },
  },
  "sm": {
    value: {
      fontFamily: "body",
      fontSize: "sm",
      fontWeight: "normal",
      lineHeight: "short",
      letterSpacing: "0",
    },
  },
  "sm.medium": {
    value: {
      fontFamily: "body",
      fontSize: "sm",
      fontWeight: "medium",
      lineHeight: "short",
      letterSpacing: "0",
    },
  },
  "md": {
    value: {
      fontFamily: "body",
      fontSize: "md",
      fontWeight: "normal",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  "md.semibold": {
    value: {
      fontFamily: "body",
      fontSize: "md",
      fontWeight: "semibold",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  brand: {
    value: {
      fontFamily: "heading",
      fontSize: "3xl",
      fontWeight: "semibold",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  "brand.subtitle": {
    value: {
      fontFamily: "body",
      fontSize: "md",
      fontWeight: "normal",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  pageTitle: {
    value: {
      fontFamily: "heading",
      fontSize: "3xl",
      fontWeight: "semibold",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  sectionTitle: {
    value: {
      fontFamily: "heading",
      fontSize: "xl",
      fontWeight: "semibold",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  cardTitle: {
    value: {
      fontFamily: "heading",
      fontSize: "xl",
      fontWeight: "semibold",
      lineHeight: "normal",
      letterSpacing: "0",
    },
  },
  muted: {
    value: {
      fontFamily: "body",
      fontSize: "sm",
      fontWeight: "normal",
      lineHeight: "short",
      letterSpacing: "0",
    },
  },
} as const;
