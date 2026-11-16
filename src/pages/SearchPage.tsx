import { useEffect, useState } from "react";
import { api } from "../api";
import type { EvidenceResult, SearchResponse, StructuredQuery, TargetCondition } from "../types";
import { ClassTag, Empty, Notice, ParamStrip, SyntheticTag, pct } from "../components/ui";
import type { PageKey } from "../App";

const EXAMPLE = "Find microgravity experiments relevant to solid-material flame spread and identify which measurements are available for comparing experimental conditions.";

export default function SearchPage({ last, setLast, go }: { last: SearchResponse | null; setLast: (s: SearchResponse) => void; go: (p: PageKey) => void }) {
  const [text, setText] = useState(last?.query.text ?? "");
  const [q, setQ] = useState<StructuredQuery | null>(last?.query ?? null);
  const [vars, setVars] = useState<{ key: string; label: string }[]>([]);
  const [targets, setTargets] = useState<{ key: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => { api.variables().then((v) => { setVars(v.measurements); setTargets(v.targets); }).catch((e) => setErr(e.message)); }, []);

  async function interpret() {
    setErr(""); setBusy(true);
    try { setQ(await api.parse(text)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  async function run() {
    if (!q) return; setErr(""); setBusy(true);
    try { setLast(await api.search(q)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  const upd = (patch: Partial<StructuredQuery>) => q && setQ({ ...q, ...patch });
  const upT = (i: number, patch: Partial<TargetCondition>) => q && upd({ target_conditions: q.target_conditions.map((t, k) => (k === i ? { ...t, ...patch } : t)) });

  return (
    <>
      <h1>Evidence search</h1>
      <p className="lede">One question type: flame spread. The search reads only what is in the imported files and explains every ranking.</p>
      <div className="card">
        <label htmlFor="qt">Research question</label>
        <textarea id="qt" value={text} onChange={(e) => setText(e.target.value)} placeholder={EXAMPLE} />
        <div className="actions">
          <button className="btn" disabled={busy || text.trim().length < 3} onClick={interpret}>Interpret question</button>
          <button className="btn ghost" onClick={() => setText(EXAMPLE)}>Use example question</button>
        </div>
      </div>
      {err && <Notice kind="err">{err}</Notice>}
      {q && (
        <div className="card">
          <h2>Structured query</h2>
          <p className="lede">Check this before searching. Interpretation only picks out keywords; it never invents numbers or conditions.</p>
          <div className="cols">
            <div>
              <label htmlFor="mat">Material or fuel (optional)</label>
              <input id="mat" value={q.material ?? ""} onChange={(e) => upd({ material: e.target.value || null })} placeholder="e.g. PMMA" />
              <label>Required measurements (default: flame spread rate)</label>
              {vars.map((v) => (
                <label key={v.key} style={{ margin: 0 }}><input type="checkbox" style={{ width: "auto" }} checked={q.required_measurements.includes(v.key)}
                  onChange={(e) => upd({ required_measurements: e.target.checked ? [...q.required_measurements, v.key] : q.required_measurements.filter((k) => k !== v.key) })} /> {v.label}</label>))}
            </div>
            <div>
              <label htmlFor="env">Mission environment (your assumption)</label>
              <select id="env" value={q.environment.name ?? ""} onChange={(e) => upd({ environment: { name: (e.target.value || null) as StructuredQuery["environment"]["name"], provenance: "USER_ASSUMED" } })}>
                <option value="">Not specified</option><option value="ISS">International Space Station</option><option value="LUNAR_HABITAT">Lunar habitat</option>
                <option value="MARS_TRANSIT">Mars transit</option><option value="CUSTOM">Custom</option></select>
              <p className="lede" style={{ marginTop: ".4rem" }}>Choosing an environment fills in no physical values. Environments are not interchangeable.</p>
              <label><input type="checkbox" style={{ width: "auto" }} checked={q.include_synthetic} onChange={(e) => upd({ include_synthetic: e.target.checked })} /> Include synthetic test files</label>
            </div>
          </div>
          <h3 style={{ marginTop: "1rem" }}>Target conditions (optional)</h3>
          {q.target_conditions.map((t, i) => (
            <div key={i} className="pair" style={{ gridTemplateColumns: "1.3fr 1fr 1fr 90px auto", marginBottom: ".4rem" }}>
              <select aria-label="Variable" value={t.variable} onChange={(e) => upT(i, { variable: e.target.value })}>{targets.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}</select>
              <input aria-label="Value" type="number" step="any" value={t.value} onChange={(e) => upT(i, { value: Number(e.target.value) })} />
              <input aria-label="Unit" value={t.unit} placeholder="unit" onChange={(e) => upT(i, { unit: e.target.value })} />
              <input aria-label="Tolerance percent" type="number" min={1} max={100} value={t.tolerance_pct} onChange={(e) => upT(i, { tolerance_pct: Number(e.target.value) })} />
              <button className="btn ghost small" onClick={() => upd({ target_conditions: q.target_conditions.filter((_, k) => k !== i) })}>Remove</button>
            </div>))}
          <p className="lede">Columns are compared only when the file documents the same unit. Tolerance is in percent.</p>
          <div className="actions">
            <button className="btn ghost" onClick={() => upd({ target_conditions: [...q.target_conditions, { variable: "pressure", value: 101.3, unit: "kPa", tolerance_pct: 10 }] })}>Add target condition</button>
            <button className="btn" disabled={busy || q.target_conditions.some((t) => !t.unit.trim())} onClick={run}>{busy ? "Searching..." : "Search evidence"}</button>
          </div>
        </div>
      )}
      {last && <Results res={last} go={go} />}
    </>
  );
}

function Results({ res, go }: { res: SearchResponse; go: (p: PageKey) => void }) {
  return (
    <>
      <h2>Ranked evidence</h2>
      <p className="lede">Ranking: class first (DIRECT, ANALOGOUS, LIMITED, UNKNOWN), then relevance, then coverage. Application heuristic, not scientifically validated.</p>
      {res.results.length === 0 ? <Empty><b>Not found in the indexed corpus.</b> No source files are indexed. Import data first.</Empty> :
        res.results.map((r) => <Result key={r.source_file_id} r={r} />)}
      <div className="actions">
        <button className="btn ghost" onClick={() => go("gaps")}>View evidence gaps</button>
        <button className="btn" onClick={() => go("brief")}>Open mission evidence brief</button>
      </div>
    </>
  );
}

function Result({ r }: { r: EvidenceResult }) {
  return (
    <div className={`card result ${r.classification} ${r.is_synthetic ? "syn" : ""}`}>
      <div className="head"><span className="num">#{r.rank}</span><ClassTag c={r.classification} />{r.is_synthetic && <SyntheticTag />}
        <span className="tag">{r.provenance_label}</span>
        <h3 style={{ margin: 0 }}>{r.investigation_title}</h3></div>
      <div className="lede">File {r.source_filename} | relevance {pct(r.relevance)} | coverage {pct(r.coverage)} | parseability {pct(r.data_quality.parseability)} | completeness {pct(r.data_quality.completeness_mapped_columns)}</div>
      <ParamStrip r={r} />
      <p><b>Why this class.</b> {r.reasons.join(" ")}</p>
      <p><b>Matching:</b> {r.matching.join(", ") || "none"}. <b>Missing:</b> {r.missing.join(", ") || "none"}. <b>Mismatches:</b> {r.mismatches.join(", ") || "none"}.</p>
      <details><summary>Parameter details and score</summary>
        <p className="lede">{r.explanation} {r.records_scored} record(s) scored; {r.records_excluded_malformed} malformed excluded.</p>
        <p>Traceable records: {r.record_references.map((x) => `#${x.record_number} (lines ${x.line_start}–${x.line_end})`).join(", ") || "none"}.</p>
        <div className="scroll"><table><thead><tr><th>Parameter</th><th>Status</th><th>Column</th><th>Unit</th><th>Weight</th><th>Match</th><th>Note</th></tr></thead>
          <tbody>{r.parameters.map((p) => <tr key={p.variable}><td>{p.label}</td><td>{p.status}</td><td>{p.column ?? "-"}</td><td>{p.variable === "material" ? "text" : (p.unit ?? "undocumented")}</td>
            <td className="num">{p.weight}</td><td className="num">{p.match === null ? "n/a" : p.match.toFixed(2)}</td><td>{p.note}</td></tr>)}</tbody></table></div>
        <div className="hash" style={{ marginTop: ".5rem" }}>SHA-256 {r.sha256}</div></details>
    </div>
  );
}
