import type { CompanyLifecycle, Drift } from "./types";

export type SyncDisplay = {
  label: string;
  tone: "green" | "orange" | "red" | "purple";
};

export function driftActive(drift: Drift | null | undefined): boolean {
  if (!drift) return false;
  return (
    drift.campaign_missing ||
    drift.offers ||
    drift.geo ||
    drift.traffic ||
    drift.streams
  );
}

/** Sync badge for company card / editor (local draft + tracker drift). */
export function syncDisplayForCard(
  lifecycle: CompanyLifecycle,
  drift: Drift | null | undefined,
  draftDirty = false,
): SyncDisplay | null {
  if (draftDirty) {
    return { label: "updating", tone: "orange" };
  }
  if (driftActive(drift)) {
    return { label: "drift", tone: "orange" };
  }
  if (lifecycle === "ready") {
    return { label: "synced", tone: "green" };
  }
  return null;
}
