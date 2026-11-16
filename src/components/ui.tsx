import type { ReactNode } from "react";
import type { EvidenceClass, EvidenceResult } from "../types";

export const SyntheticTag = () => <span className="tag syn" title="Fabricated test data">SYNTHETIC - NOT NASA DATA</span>;
export const ClassTag = ({ c }: { c: EvidenceClass }) => <span className={`tag ${c}`}>{c}</span>;
export const Prov = ({ p }: { p: string }) => <span className={`tag ${p}`}>{p}</span>;

export function Notice({ kind, children }: { kind: "err" | "ok" | "warn" | ""; children: ReactNode }) {
  return <div className={`notice ${kind}`} role={kind === "err" ? "alert" : "status"}>{children}</div>;
}
export const Empty = ({ children }: { children: ReactNode }) => <div className="empty">{children}</div>;
export const Loading = () => <p className="lede" role="status">Loading...</p>;

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <div className="stat"><b>{value}</b><span>{label}</span></div>;
}

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "n/a" : `${Math.round(v * 100)}%`);

/** One segment per requested parameter. Width follows the parameter weight; fill shows the match. */
export function ParamStrip({ r }: { r: EvidenceResult }) {
  return (
    <div>
      <div className="strip" role="img" aria-label={`Coverage ${pct(r.coverage)} of requested parameters`}>
        {r.parameters.map((p) => {
          const fill = p.available ? (p.match ?? 1) : 0;
          const cls = p.status === "MISMATCH" ? "mism" : fill < 1 ? "partial" : "";
          return <div key={p.variable} className={`seg ${cls}`} style={{ ["--w" as string]: p.weight }} title={`${p.label}: ${p.status}`}>
            <i style={{ width: `${fill * 100}%` }} /></div>;
        })}
      </div>
      <div className="legend">Each block is one requested parameter (wider = higher weight). Hatched = not available. Red = mismatch.</div>
    </div>
  );
}

