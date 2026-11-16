import { useEffect, useState } from "react";
import { api } from "../api";
import type { Dashboard as D } from "../types";
import { Empty, Loading, Notice, Stat, SyntheticTag } from "../components/ui";
import type { PageKey } from "../App";

export default function Dashboard({ go, onChange }: { go: (p: PageKey) => void; onChange: () => void }) {
  const [d, setD] = useState<D | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { api.dashboard().then(setD).catch((e) => setErr(e.message)); }, []);

  async function demo() {
    setErr(""); setMsg("");
    try { const r = await api.loadSynthetic(); setMsg(r.created ? "Synthetic demo file loaded." : "Synthetic demo file was already loaded."); onChange(); }
    catch (e) { setErr((e as Error).message); }
  }
  if (err && !d) return <Notice kind="err">{err}</Notice>;
  if (!d) return <Loading />;
  return (
    <>
      <h1>Dashboard</h1>
      <p className="lede">What is indexed in this installation. Nothing here comes from NASA unless you imported it yourself.</p>
      {err && <Notice kind="err">{err}</Notice>}{msg && <Notice kind="ok">{msg}</Notice>}
      <div className="stats">
        <Stat label="Investigations" value={d.investigations} /><Stat label="Source files" value={d.source_files} />
        <Stat label="Records" value={d.records} /><Stat label="Malformed records" value={d.malformed_records} />
        <Stat label="User-imported files (source unverified)" value={d.user_imported_files} /><Stat label="Synthetic demo files" value={d.synthetic_files} />
      </div>
      {d.source_files === 0 ? (
        <Empty>
          <p><b>No data is indexed yet.</b> Import a CSV from NASA Physical Sciences Informatics, or load the synthetic demo to try the workflow.</p>
          <div className="actions">
            <button className="btn" onClick={() => go("import")}>Import a CSV</button>
            <button className="btn ghost" onClick={demo}>Load synthetic demo</button>
          </div>
        </Empty>
      ) : (
        <div className="card">
          <h2>Recent imports</h2>
          <div className="scroll"><table>
            <thead><tr><th>File</th><th>Records</th><th>Parse status</th><th>Mapped columns</th><th></th></tr></thead>
            <tbody>{d.recent_files.map((f) => (
              <tr key={f.id}><td>{f.filename}<div className="hash">{f.sha256}</div></td><td className="num">{f.row_count}</td>
                <td>{f.parse_status}</td><td className="num">{Object.keys(f.column_map).length} of {f.columns.length}</td>
                <td>{f.is_synthetic && <SyntheticTag />}</td></tr>))}</tbody>
          </table></div>
          <div className="actions"><button className="btn ghost" onClick={demo}>Load synthetic demo</button>
            <button className="btn" onClick={() => go("search")}>Search evidence</button></div>
        </div>
      )}
    </>
  );
}
