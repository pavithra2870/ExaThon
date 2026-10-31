import { createContext, useContext } from "react";
import { useSearchParams } from "react-router-dom";

export const DatasetsContext = createContext({ list: [], loading: true, error: null });

/** Current dataset from ?ds=, falling back to the first processed one. */
export function useDataset() {
  const { list } = useContext(DatasetsContext);
  const [params, setParams] = useSearchParams();
  const requested = params.get("ds");
  const fallback = list.find((d) => d.ready) ?? list[0];
  const current = list.find((d) => d.id === requested) ?? fallback ?? null;
  const setDataset = (id) => {
    const next = new URLSearchParams(params);
    next.set("ds", id);
    setParams(next);
  };
  return { ds: current, id: current?.id ?? null, setDataset, list };
}

export const GROUP_ORDER = ["tipped", "anyway", "never", "put_off"];

export const GROUP_COPY = {
  tipped: { label: "Offer tips them", short: "Tipped", hint: "estimated to act only because of the message" },
  anyway: { label: "Would act anyway", short: "Anyway", hint: "likely to act without the message; little estimated effect" },
  never: { label: "Won't act either way", short: "Won't act", hint: "unlikely to act, message or not" },
  put_off: { label: "Offer puts them off", short: "Put off", hint: "estimated to act less when messaged" },
};
