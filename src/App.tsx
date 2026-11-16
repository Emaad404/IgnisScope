import { useState } from "react";
import type { SearchResponse } from "./types";
import Dashboard from "./pages/Dashboard";
import Explorer from "./pages/Explorer";
import ImportPage from "./pages/ImportPage";
import SearchPage from "./pages/SearchPage";
import GapsPage from "./pages/GapsPage";
import BriefPage from "./pages/BriefPage";

const PAGES = [
  ["dashboard", "Dashboard"], ["explorer", "Investigation explorer"], ["import", "Import data"],
  ["search", "Evidence search"], ["gaps", "Evidence gaps"], ["brief", "Mission evidence brief"],
] as const;
export type PageKey = (typeof PAGES)[number][0];

export default function App() {
  const [page, setPage] = useState<PageKey>("dashboard");
  const [last, setLast] = useState<SearchResponse | null>(null);
  const [refresh, setRefresh] = useState(0);
  const bump = () => setRefresh((n) => n + 1);

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">Flame in Freefall<small>Mission evidence intelligence</small></div>
        <nav className="nav" aria-label="Main">
          {PAGES.map(([k, label]) => (
            <button key={k} onClick={() => setPage(k)} aria-current={page === k ? "page" : undefined}>{label}</button>
          ))}
        </nav>
        <div className="foot">Research-support tool. Not a certified fire-risk predictor. Not endorsed by NASA.</div>
      </aside>
      <main>
        {page === "dashboard" && <Dashboard key={refresh} go={setPage} onChange={bump} />}
        {page === "explorer" && <Explorer key={refresh} />}
        {page === "import" && <ImportPage onChange={bump} />}
        {page === "search" && <SearchPage last={last} setLast={setLast} go={setPage} />}
        {page === "gaps" && <GapsPage last={last} go={setPage} />}
        {page === "brief" && <BriefPage last={last} go={setPage} />}
      </main>
    </div>
  );
}
