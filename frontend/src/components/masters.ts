// Master lists (districts, mandals, skills, …) for forms. Cached for the session so forms open quickly on slow networks.
import { useEffect, useState } from "react";
import { api, type MasterOpt } from "../api";

const cache = new Map<string, Promise<MasterOpt[]>>();

export function loadMaster(kind: string, parent?: string | null): Promise<MasterOpt[]> {
  const key = `${kind}:${parent ?? ""}`;
  if (!cache.has(key)) {
    const p = api<MasterOpt[]>(`/masters?kind=${kind}${parent ? `&parent=${encodeURIComponent(parent)}` : ""}`);
    p.catch(() => cache.delete(key));
    cache.set(key, p);
  }
  return cache.get(key)!;
}

/** Forget cached lists (after an admin edits master data). */
export const clearMasterCache = () => cache.clear();

/** Items plus whether the list has finished loading (an empty list that is still loading is not "no items"). */
export function useMasterList(kind: string, parent?: string | null, enabled = true): [MasterOpt[], boolean] {
  const [state, setState] = useState<{ key: string; items: MasterOpt[] }>({ key: "", items: [] });
  const key = enabled ? `${kind}:${parent ?? ""}` : "";
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    loadMaster(kind, parent).then((x) => live && setState({ key, items: x })).catch(() => live && setState({ key, items: [] }));
    return () => {
      live = false;
    };
  }, [kind, parent, enabled, key]);
  const loaded = !enabled || state.key === key;
  return [loaded && enabled ? state.items : [], loaded];
}

export function useMaster(kind: string, parent?: string | null, enabled = true): MasterOpt[] {
  return useMasterList(kind, parent, enabled)[0];
}
