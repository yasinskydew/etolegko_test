import type { OfferRow } from "./types";

export type CompanyDraft = {
  geo_codes: string[];
  offers: OfferRow[];
};

function key(companyId: number): string {
  return `etolegko:company-draft:${companyId}`;
}

export function readCompanyDraft(companyId: number): CompanyDraft | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(key(companyId));
    if (!raw) return null;
    return JSON.parse(raw) as CompanyDraft;
  } catch {
    return null;
  }
}

export function writeCompanyDraft(
  companyId: number,
  draft: CompanyDraft,
): void {
  localStorage.setItem(key(companyId), JSON.stringify(draft));
}

export function clearCompanyDraft(companyId: number): void {
  localStorage.removeItem(key(companyId));
}

export function draftsEqual(
  a: CompanyDraft,
  b: CompanyDraft,
): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}
