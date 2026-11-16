import { useEffect, useState } from "react";
import { api } from "../api";
import type { Investigation, InvestigationDetail, RecordRow, SourceFile } from "../types";
import { Empty, Loading, Notice, Prov, SyntheticTag } from "../components/ui";

export default function Explorer() {
  const [q, setQ] = useState("");
  const [list, setList] = useState<Investigation[] | null>(null);
  const [sel, setSel] = useState<InvestigationDetail | null>(null);
  const [file, setFile] = useState<SourceFile | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => { const t = setTimeout(() => api.investigations(q).then(setList).catch((e) => setErr(e.message)), 200); return () => clearTimeout(t); }, [q]);
  const open = (id: number) => { setFile(null); api.investigation(id).then(setSel).catch((e) => setErr(e.message)); };

  return (
    <>
      <h1>Investigation explorer</h1>
      <label htmlFor="q">Search investigations by title, description or PSI id</label>
      <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. flame spread" />
      {err && <Notice kind="err">{err}</Notice>}
      <div className="row" style={{ marginTop: "1rem" }}>
        <div style={{ flex: "1 1 320px" }}>
          {!list ? <Loading /> : list.length === 0 ? <Empty>{q ? "No investigation matches this search." : "No investigations yet. Create one on the Import page."}</Empty> :
            list.map((i) => (
              <button key={i.id} className={`card ${i.is_synthetic ? "syn" : ""}`} style={{ width: "100%", textAlign: "left", cursor: "pointer", color: "inherit" }} onClick={() => open(i.id)}>
                <h3>{i.title}</h3>
                <div className="head">{i.is_synthetic && <SyntheticTag />}{i.psi_id && <span className="tag">{i.psi_id}</span>}
                  <span className="tag">{i.nasa_verified ? "User-attested; unverified by app" : "Source not verified"}</span>
                  <span className="tag">{i.n_files} file(s)</span></div>
              </button>))}
        </div>
        <div style={{ flex: "2 1 460px" }}>
          {!sel ? <Empty>Select an investigation to see its metadata and source files.</Empty> : (
            <>
              <div className={`card ${sel.is_synthetic ? "syn" : ""}`}>
                <h2>{sel.title}</h2>
                <div className="head">{sel.is_synthetic && <SyntheticTag />}<span>Gravity context:</span>
                  <span>{sel.gravity_context ?? "not recorded"}</span><Prov p={sel.gravity_provenance} /></div>
                {sel.description && <p>{sel.description}</p>}
                {sel.source_url && <p>Source: <a href={sel.source_url} target="_blank" rel="noreferrer">{sel.source_url}</a></p>}
              </div>
              <h3>Source files</h3>
              {sel.files.length === 0 ? <Empty>No files imported for this investigation.</Empty> : sel.files.map((f) => (
                <div key={f.id} className="card">
                  <div className="head"><b>{f.filename}</b><span className="tag">{f.parse_status}</span><span className="tag">{f.row_count} records</span></div>
                  <div className="hash">SHA-256 {f.sha256}</div>
                  <p className="lede">{f.size_bytes} bytes | {f.encoding} | delimiter {JSON.stringify(f.delimiter)} | imported {new Date(f.imported_at).toLocaleString()} | {f.pipeline_version}</p>
                  {f.warnings.length > 0 && <details><summary>{f.warnings.length} warning(s)</summary><ul>{f.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul></details>}
                  <div className="actions"><button className="btn small" onClick={() => setFile(f)}>Browse records</button></div>
                </div>))}
              {file && <Records file={file} />}
            </>)}
        </div>
      </div>
    </>
  );
}

function Records({ file }: { file: SourceFile }) {
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ total: number; records: RecordRow[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { setOffset(0); }, [file.id]);
  useEffect(() => { setData(null); api.records(file.id, offset).then(setData).catch((e) => setErr(e.message)); }, [file.id, offset]);
  return (
    <div className="card">
      <h3>Records in {file.filename}</h3>
      <p className="lede">Values are exactly as in the source file. An empty cell shows as (empty); a cell missing from a short row shows as (absent). Neither is zero.</p>
      {err && <Notice kind="err">{err}</Notice>}
      {!data ? <Loading /> : (
        <>
          <div className="scroll"><table>
            <thead><tr><th>#</th><th>Lines</th><th>Row status</th>{file.columns.map((c) => <th key={c.index}>{c.original || "(blank)"}</th>)}<th>Numeric parse status</th><th>Issues</th></tr></thead>
            <tbody>{data.records.map((r) => (
              <tr key={r.id} className={r.parse_status !== "OK" || r.issues.length ? "rowbad" : ""}>
                <td className="num">{r.record_number}</td><td className="num">{r.line_start === r.line_end ? r.line_start : `${r.line_start}-${r.line_end}`}</td>
                <td>{r.parse_status}</td>
                {r.raw_values.map((v, i) => <td key={i}>{v === null ? <i>(absent)</i> : v === "" ? <i>(empty)</i> : v}</td>)}
                <td>{Object.entries(r.numeric_status).map(([key, value]) => `${key}: ${value}`).join("; ") || "—"}</td>
                <td>{[...r.issues, ...(r.extra_cells.length ? [`extra cells: ${r.extra_cells.join(" | ")}`] : [])].join(" ")}</td></tr>))}</tbody>
          </table></div>
          <div className="actions">
            <button className="btn ghost small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</button>
            <span className="lede">{data.total === 0 ? "0 records" : `${offset + 1}-${Math.min(offset + 25, data.total)} of ${data.total}`}</span>
            <button className="btn ghost small" disabled={offset + 25 >= data.total} onClick={() => setOffset(offset + 25)}>Next</button>
          </div>
        </>)}
    </div>
  );
}
