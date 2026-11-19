import type { Drift, SyncStatus } from "./types";

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

/** Sync badge for company card / editor (local sync + tracker drift from GET). */
export function syncDisplayForCard(
  sync: SyncStatus,
  drift: Drift | null | undefined,
): SyncDisplay | null {
  if (sync === "update_mode") {
    return { label: "update mode", tone: "orange" };
  }
  if (driftActive(drift)) {
    return { label: "drift", tone: "orange" };
  }
  if (sync === "synced") {
    return { label: "synced", tone: "green" };
  }
  return null;
}
