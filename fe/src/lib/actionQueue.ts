export type QueueAction =
  | { action: "add"; offer_id: number; percent?: number }
  | { action: "remove"; offer_id: number }
  | { action: "restore"; offer_id: number }
  | { action: "pin"; offer_id: number }
  | { action: "unpin"; offer_id: number }
  | { action: "set_percent"; offer_id: number; percent: number };

export type QueuedItem = QueueAction & {
  id: string;
  createdAt: number;
};

function queueKey(companyId: number, tabId: string): string {
  return `company:${companyId}:tab:${tabId}`;
}

export function getTabId(): string {
  if (typeof window === "undefined") return "ssr";
  const KEY = "etolegko:tabId";
  let id = sessionStorage.getItem(KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(KEY, id);
  }
  return id;
}

export function readQueue(companyId: number, tabId: string): QueuedItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(queueKey(companyId, tabId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as QueuedItem[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function writeQueue(
  companyId: number,
  tabId: string,
  items: QueuedItem[],
): void {
  localStorage.setItem(queueKey(companyId, tabId), JSON.stringify(items));
}

export function enqueueAction(
  companyId: number,
  tabId: string,
  action: QueueAction,
): QueuedItem {
  const items = readQueue(companyId, tabId);
  const item: QueuedItem = {
    ...action,
    id: crypto.randomUUID(),
    createdAt: Date.now(),
  };
  items.push(item);
  writeQueue(companyId, tabId, items);
  return item;
}

export function removeQueued(
  companyId: number,
  tabId: string,
  itemIds: string[],
): void {
  const set = new Set(itemIds);
  const next = readQueue(companyId, tabId).filter((i) => !set.has(i.id));
  writeQueue(companyId, tabId, next);
}

export function clearQueue(companyId: number, tabId: string): void {
  localStorage.removeItem(queueKey(companyId, tabId));
}

export function isQueueDirty(companyId: number, tabId: string): boolean {
  return readQueue(companyId, tabId).length > 0;
}
