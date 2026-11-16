import { useMemo, useState } from "react";
import type { SearchResponse } from "../types";
import { Empty, SyntheticTag } from "../components/ui";
import type { PageKey } from "../App";

export default function GapsPage({ last, go }: { last: SearchResponse | null; go: (p: PageKey) => void }) {
  const [cat, setCat] = useState("");
  const cats = useMemo(() => [...new Set((last?.results ?? []).flatMap((r) => r.gaps.map((g) => g.category)))], [last]);
  if (!last) return <><h1>Evidence gaps</h1><Empty><p>Run an evidence search first. Gaps are computed from its results.</p><button className="btn" onClick={() => go("search")}>Go to evidence search</button></Empty></>;
  return (
    <>
      <h1>Evidence gaps</h1>
      <p className="lede">A gap means the item was not found in the indexed file. It does not mean the experiment did not measure it, and a missing value is never treated as zero.</p>
      <label htmlFor="c">Filter by category</label>
      <select id="c" value={cat} onChange={(e) => setCat(e.target.value)} style={{ maxWidth: 320 }}>
        <option value="">All categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</select>
      {last.results.length === 0 ? <Empty>Not found in the indexed corpus. Nothing is indexed.</Empty> : last.results.map((r) => {
        const gaps = r.gaps.filter((g) => !cat || g.category === cat);
        return (
          <div key={r.source_file_id} className="card" style={{ marginTop: "1rem" }}>
            <div className="head"><h3 style={{ margin: 0 }}>{r.source_filename}</h3>{r.is_synthetic && <SyntheticTag />}</div>
            {gaps.length === 0 ? <p className="lede">No gaps in this category for this file.</p> : (
              <div className="scroll"><table><thead><tr><th>Parameter</th><th>Category</th><th>Status</th><th>Unit</th><th>Value found</th><th>Detail</th><th>Interpretation limit</th></tr></thead>
                <tbody>{gaps.map((g, i) => <tr key={i}><td>{g.parameter}</td><td>{g.category}</td><td>{g.status}</td><td>{g.unit ?? "-"}</td>
                  <td className="num">{g.value ? JSON.stringify(g.value) : "not available"}</td><td>{g.detail}</td><td>{g.limitation}</td></tr>)}</tbody></table></div>)}
          </div>);
      })}
    </>
  );
}
