import { useEffect, useState } from "react";
import { api } from "../api";
import type { Investigation, Provenance, SourceFile } from "../types";
import { Notice, Prov, SyntheticTag } from "../components/ui";

export default function ImportPage({ onChange }: { onChange: () => void }) {
  const [invs, setInvs] = useState<Investigation[]>([]);
  const [invId, setInvId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [units, setUnits] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState<SourceFile | null>(null);
  const reload = () => api.investigations().then(setInvs).catch((e) => setErr(e.message));
  useEffect(() => { reload(); }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setDone(null);
    if (!file || invId === "") return;
    let overrides: string | undefined;
    if (units.trim()) {
      const map: Record<string, string> = {};
      for (const line of units.split("\n")) { const [k, v] = line.split("="); if (k && v) map[k.trim()] = v.trim(); }
      overrides = JSON.stringify(map);
    }
    const form = new FormData();
    form.append("file", file); form.append("investigation_id", String(invId));
    if (url) form.append("source_url", url);
    if (overrides) form.append("unit_overrides", overrides);
    setBusy(true);
    try { setDone(await api.importFile(form)); onChange(); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  }

  return (
    <>
      <h1>Import data</h1>
      <p className="lede">Upload a CSV from NASA Physical Sciences Informatics (or another source you can cite). The original file is stored unchanged and fingerprinted with SHA-256.</p>
      <div className="row">
        <form className="card" onSubmit={submit}>
          <h2>Upload a CSV</h2>
          <label htmlFor="inv">Investigation</label>
          <select id="inv" value={invId} onChange={(e) => setInvId(e.target.value ? Number(e.target.value) : "")} required>
            <option value="">Choose an investigation</option>
            {invs.map((i) => <option key={i.id} value={i.id}>{i.is_synthetic ? "[SYNTHETIC] " : ""}{i.title}</option>)}
          </select>
          <label htmlFor="f">CSV file (.csv, .tsv, .txt)</label>
          <input id="f" type="file" accept=".csv,.tsv,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
          <label htmlFor="u">Source URL (where you downloaded it)</label>
          <input id="u" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://psi.nasa.gov/..." />
          <label htmlFor="o">Unit overrides, one per line, for columns whose header has no unit</label>
          <textarea id="o" value={units} onChange={(e) => setUnits(e.target.value)} placeholder={"Pressure=kPa\nFlow=cm/s"} />
          <p className="lede">Units you type here are recorded as USER_SUPPLIED, not as source-supported.</p>
          <div className="actions"><button className="btn" disabled={busy || !file || invId === ""}>{busy ? "Importing..." : "Import file"}</button></div>
          {err && <Notice kind="err">{err}</Notice>}
        </form>
        <NewInvestigation onCreated={(i) => { reload(); setInvId(i.id); }} />
      </div>
      {done && (
        <div className="card">
          <h2>Import result</h2>
          <Notice kind={done.parse_status === "OK" ? "ok" : "warn"}>{done.filename} imported: {done.row_count} record(s), parse status {done.parse_status}.</Notice>
          <div className="hash">SHA-256 {done.sha256}</div>
          <p className="lede">Quality indicators (kept separate, not combined): parseability {done.data_quality.parseability ?? "n/a"}, completeness of mapped columns {done.data_quality.completeness_mapped_columns ?? "n/a"}, unit completeness {done.data_quality.unit_completeness ?? "n/a"}.</p>
          <h3>Columns</h3>
          <div className="scroll"><table><thead><tr><th>#</th><th>Original header</th><th>Unit</th><th>Recognised as</th></tr></thead>
            <tbody>{done.columns.map((c) => <tr key={c.index}><td>{c.index + 1}</td><td>{c.original || "(blank)"}</td>
              <td>{c.unit ?? <i>undocumented</i>} {c.unit_source === "USER_SUPPLIED" && <Prov p="USER_ASSUMED" />}</td><td>{c.canonical ?? <i>not mapped, kept as-is</i>}</td></tr>)}</tbody></table></div>
          {done.warnings.length > 0 && <><h3>Parsing warnings</h3><ul>{done.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></>}
          {done.is_synthetic && <SyntheticTag />}
        </div>
      )}
    </>
  );
}

function NewInvestigation({ onCreated }: { onCreated: (i: Investigation) => void }) {
  const [t, setT] = useState(""); const [psi, setPsi] = useState(""); const [desc, setDesc] = useState("");
  const [url, setUrl] = useState(""); const [verified, setVerified] = useState(false); const [syn, setSyn] = useState(false);
  const [g, setG] = useState(""); const [gp, setGp] = useState<Provenance>("UNKNOWN");
  const [err, setErr] = useState(""); const [ok, setOk] = useState("");
  async function go(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setOk("");
    try {
      const i = await api.createInvestigation({ title: t, psi_id: psi || null, description: desc || null, source_url: url || null,
        nasa_verified: verified, is_synthetic: syn, gravity_context: g || null, gravity_provenance: g ? gp : "UNKNOWN" });
      setOk(`Created "${i.title}".`); setT(""); onCreated(i);
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <form className="card" onSubmit={go}>
      <h2>New investigation</h2>
      <label htmlFor="t">Title (as shown on the NASA page)</label><input id="t" value={t} onChange={(e) => setT(e.target.value)} required minLength={3} />
      <label htmlFor="p">PSI id (only if you checked it)</label><input id="p" value={psi} onChange={(e) => setPsi(e.target.value)} placeholder="optional" />
      <label htmlFor="d">Description</label><textarea id="d" value={desc} onChange={(e) => setDesc(e.target.value)} />
      <label htmlFor="s">Investigation page URL</label><input id="s" value={url} onChange={(e) => setUrl(e.target.value)} />
      <label htmlFor="g">Gravity context documented by the source (leave empty if unknown)</label>
      <input id="g" value={g} onChange={(e) => setG(e.target.value)} placeholder="e.g. microgravity on ISS" />
      {g && <><label htmlFor="gp">Where does that come from?</label>
        <select id="gp" value={gp} onChange={(e) => setGp(e.target.value as Provenance)}>
          <option value="SOURCE_SUPPORTED">The source document states it</option><option value="USER_ASSUMED">My assumption</option></select></>}
      <label><input type="checkbox" style={{ width: "auto" }} checked={verified} onChange={(e) => setVerified(e.target.checked)} /> I attest I checked this record against a NASA page (the app cannot independently verify this)</label>
      <label><input type="checkbox" style={{ width: "auto" }} checked={syn} onChange={(e) => setSyn(e.target.checked)} /> This is synthetic test data</label>
      <div className="actions"><button className="btn ghost">Create investigation</button></div>
      {err && <Notice kind="err">{err}</Notice>}{ok && <Notice kind="ok">{ok}</Notice>}
    </form>
  );
}
