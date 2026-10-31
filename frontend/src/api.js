import { useCallback, useEffect, useRef, useState } from "react";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";
const cache = new Map();

export class ApiError extends Error {
  constructor(message, hint, status) {
    super(message);
    this.hint = hint;
    this.status = status;
  }
}

function url(path, params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, v);
  }
  const s = qs.toString();
  return `${BASE}${path}${s ? `?${s}` : ""}`;
}

export async function get(path, params) {
  let res;
  try {
    res = await fetch(url(path, params));
  } catch {
    throw new ApiError(
      "Can't reach the PromoLens API.",
      "Start it from backend/ with: uvicorn app.main:app --reload",
      0,
    );
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error page */
  }
  if (!res.ok) {
    throw new ApiError(
      body?.error ?? `The API answered ${res.status}.`,
      body?.hint ?? "Check the backend log, then try again.",
      res.status,
    );
  }
  return body;
}

/** Fetch with a session cache. Pass path = null to skip. */
export function useApi(path, params, { cache: useCache = true } = {}) {
  const key = path ? url(path, params) : null;
  const [state, setState] = useState(() => ({
    data: key && useCache ? cache.get(key) ?? null : null,
    error: null,
    loading: Boolean(key) && !(useCache && cache.has(key)),
  }));
  const seq = useRef(0);

  const load = useCallback(
    async (force = false) => {
      if (!key) return;
      if (!force && useCache && cache.has(key)) {
        setState({ data: cache.get(key), error: null, loading: false });
        return;
      }
      const id = ++seq.current;
      setState((s) => ({ data: s.data, error: null, loading: true }));
      try {
        const data = await get(path, params);
        if (useCache) cache.set(key, data);
        if (id === seq.current) setState({ data, error: null, loading: false });
      } catch (error) {
        if (id === seq.current) setState({ data: null, error, loading: false });
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key],
  );

  useEffect(() => {
    load();
  }, [load]);

  return { ...state, reload: () => load(true) };
}
