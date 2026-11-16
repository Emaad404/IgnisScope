import { useEffect, useState } from "react";
import { api } from "../api";
import type { EvidenceResult, SearchResponse } from "../types";
import { ClassTag, Empty, Loading, Notice, SyntheticTag, pct } from "../components/ui";
import type { PageKey } from "../App";

interface Report {
  generated_at: string; pipeline_version: string; methodology_version: string; research_question: string;
  executive_summary: string; search_scope: { investigations_indexed: number; source_files_indexed: number; records_indexed: number };
  ranked_evidence: EvidenceResult[]; limitations: string[]; doi_note: string;
  source_references: { investigation: string; filename: string; sha256: string; source_url: string | null; is_synthetic: boolean; nasa_verified: boolean }[];
}

export default function BriefPage({ last, go }: { last: SearchResponse | null; go: (p: PageKey) => void }) {
  const [rep, setRep] = useState<Report | null>(null);
  const [err, setErr] = useState("");
  const id = last?.question_id;
  useEffect(() => { if (id) { setRep(null); api.report(id).then((r) => setRep(r as unknown as Report)).catch((e) => setErr(e.message)); } }, [id]);
  if (!last) return <><h1>Mission evidence brief</h1><Empty><p>Run an evidence search first. The brief is generated from its results.</p><button className="btn" onClick={() => go("search")}>Go to evidence search</button></Empty></>;
  if (err) return <Notice kind="err">{err}</Notice>;
  if (!rep) return <Loading />;
  return (
    <>
      <h1>Mission evidence brief</h1>
      <div className="actions" style={{ marginBottom: "1rem" }}>
        <a className="btn" href={`/api/reports/${id}/pdf`} download>Download PDF</a>
        <a className="btn ghost" href={`/api/reports/${id}?download=true`} download>Download JSON</a>
      </div>
      <p className="lede">Generated {new Date(rep.generated_at).toLocaleString()} | {rep.pipeline_version} | {rep.methodology_version}</p>
      <div className="card"><h2>Research question</h2><p>{rep.research_question}</p></div>
      <div className="card"><h2>Executive summary</h2><p>{rep.executive_summary}</p>
        <p className="lede">Scope: {rep.search_scope.investigations_indexed} investigation(s), {rep.search_scope.source_files_indexed} file(s), {rep.search_scope.records_indexed} record(s) indexed.</p></div>
      <div className="card"><h2>Ranked evidence</h2>
        {rep.ranked_evidence.length === 0 ? <p>Not found in the indexed corpus.</p> : (
          <div className="scroll"><table><thead><tr><th>Rank</th><th>Class</th><th>Investigation / file</th><th>Relevance</th><th>Coverage</th><th>Reasons</th></tr></thead>
            <tbody>{rep.ranked_evidence.map((r) => <tr key={r.source_file_id}><td className="num">{r.rank}</td><td><ClassTag c={r.classification} /></td>
              <td>{r.investigation_title} {r.is_synthetic && <SyntheticTag />}<div className="hash">{r.source_filename}</div></td>
              <td className="num">{pct(r.relevance)}</td><td className="num">{pct(r.coverage)}</td><td>{r.reasons.join(" ")}</td></tr>)}</tbody></table></div>)}
      </div>
      <div className="card"><h2>Limitations</h2><ul>{rep.limitations.map((l) => <li key={l}>{l}</li>)}</ul></div>
      <div className="card"><h2>Source references</h2>
        {rep.source_references.length === 0 ? <p>None.</p> : rep.source_references.map((s) => (
          <p key={s.sha256}>{s.investigation}, {s.filename} {s.is_synthetic ? <SyntheticTag /> : <span className="tag">{s.nasa_verified ? "User-attested; unverified by app" : "Source not verified"}</span>}
            <br /><span className="hash">SHA-256 {s.sha256}</span><br /><span className="lede">{s.source_url ?? "no URL recorded"}</span></p>))}
        <p className="lede">{rep.doi_note}</p></div>
    </>
  );
}
