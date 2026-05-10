import { useEffect, useState, useCallback } from "react";
import {
  FolderKanban, Building2, FileSignature, Calendar, Clock, FileText, Search,
} from "lucide-react";
import { rpc } from "../../api/rpc";
import { str, int, entity, dateRange, projectStatus } from "../../api/entity";
import { StatusBadge } from "../shared/StatusBadge";
import { ViewModeToggle } from "../shared/ViewModeToggle";
import { KanbanBoard, useStageStore, type BoardColumn } from "../shared/KanbanBoard";
import type { Entity } from "../../api/types";

const PROJECT_COLUMNS: BoardColumn[] = [
  { id: "Lead", label: "Lead", color: "#a855f7" },
  { id: "Offer", label: "Offer", color: "#f97316" },
  { id: "Upcoming", label: "Upcoming", color: "#3b82f6" },
  { id: "Active", label: "Active", color: "#22c55e" },
  { id: "Completed", label: "Completed", color: "#8e8e93" },
];

const STATUS_FILTERS = ["All", "Active", "Upcoming", "Completed"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];
const FILTER_COLORS: Record<string, string> = {
  All: "#007AFF", Active: "#34d399", Upcoming: "#60a5fa", Completed: "#a0a0a0",
};

export function ProjectsView() {
  const [projects, setProjects] = useState<Entity[]>([]);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"list" | "board">("list");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [search, setSearch] = useState("");

  const defaultColumn = useCallback(
    (e: { id: number; [k: string]: unknown }) =>
      PROJECT_COLUMNS.find((c) => c.id === projectStatus(e as Entity))?.id || "Active",
    [],
  );
  const stageStore = useStageStore("project", PROJECT_COLUMNS, defaultColumn);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const res = await rpc<Entity[]>("projects.get_all");
    if (res.ok && res.data) setProjects(res.data);
    setLoading(false);
  }

  function matchesSearch(p: Entity) {
    if (!search) return true;
    const q = search.toLowerCase();
    return str(p, "title").toLowerCase().includes(q) || str(p, "tag").toLowerCase().includes(q)
      || clientName(p).toLowerCase().includes(q);
  }

  const filtered = projects.filter((p) =>
    (statusFilter === "All" || projectStatus(p) === statusFilter) && matchesSearch(p));
  const boardFiltered = projects.filter(matchesSearch);

  function moveToColumn(id: number, colId: string) {
    stageStore.setColumn(id, colId);
    if (colId === "Completed") rpc("projects.toggle_completed", { id }).then(load);
    else {
      const proj = projects.find((p) => p.id === id);
      if (proj && projectStatus(proj) === "Completed") rpc("projects.toggle_completed", { id }).then(load);
    }
  }

  const contract = selected ? entity(selected, "contract") : null;
  const client = contract ? entity(contract, "client") : null;

  if (loading && projects.length === 0)
    return <div className="flex items-center justify-center h-full text-secondary">Loading projects…</div>;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 shrink-0 border-b border-border-subtle">
        <h2 className="text-sm font-semibold">Projects</h2>
        <div className="flex-1" />
        {viewMode === "list" && (
          <div className="flex items-center gap-1">
            {STATUS_FILTERS.map((s) => {
              const c = FILTER_COLORS[s];
              return (
                <button key={s} onClick={() => setStatusFilter(s)}
                  className="px-2 py-1 rounded-md text-xs font-medium transition-colors"
                  style={{
                    background: statusFilter === s ? `${c}22` : "transparent",
                    color: statusFilter === s ? c : "var(--color-tertiary)",
                    border: statusFilter === s ? `1px solid ${c}44` : "1px solid transparent",
                  }}>{s}</button>
              );
            })}
          </div>
        )}
        <ViewModeToggle mode={viewMode} onChange={setViewMode} />
        <div className="flex-1" />
        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input type="text" placeholder="Search…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 pr-3 py-1.5 rounded-md text-sm outline-none w-44 bg-bg-card text-primary border border-border-subtle placeholder:text-muted" />
        </div>
      </div>

      {viewMode === "list" ? (
        <div className="flex flex-1 overflow-hidden">
          <div className="w-72 shrink-0 flex flex-col border-r border-border-subtle">
            <div className="flex-1 overflow-y-auto">
              {filtered.length === 0
                ? <div className="p-4 text-sm text-center text-tertiary">No projects.</div>
                : filtered.map((p) => (
                  <button key={p.id} onClick={() => setSelected(p)}
                    className={`w-full text-left px-4 py-2.5 border-b border-border-subtle transition-colors ${selected?.id === p.id ? "bg-bg-selected" : "hover:bg-bg-hover"}`}>
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium truncate">{str(p, "title")}</span>
                      <StatusBadge status={projectStatus(p)} />
                    </div>
                    <div className="text-xs text-secondary mt-0.5 truncate">{str(p, "tag")}</div>
                  </button>
                ))}
            </div>
            <div className="px-4 py-2 text-xs text-tertiary border-t border-border-subtle">
              {filtered.length} project{filtered.length !== 1 ? "s" : ""}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {selected ? (
              <div className="p-6 max-w-2xl space-y-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-bg-card flex items-center justify-center">
                    <FolderKanban size={18} className="text-secondary" />
                  </div>
                  <div>
                    <h1 className="text-lg font-semibold">{str(selected, "title")}</h1>
                    <p className="text-xs text-secondary">{str(selected, "tag")}</p>
                  </div>
                  <StatusBadge status={projectStatus(selected)} className="ml-auto" />
                </div>
                {str(selected, "description") && <p className="text-sm text-secondary">{str(selected, "description")}</p>}
                <div className="grid grid-cols-2 gap-4">
                  <DetailRow label="Dates" value={dateRange(selected)} />
                  <DetailRow label="Client" value={client ? str(client, "name") : "—"} />
                  <DetailRow label="Contract" value={contract ? str(contract, "title") : "—"} />
                  <DetailRow label="Rate" value={contract ? `${str(contract, "rate")} ${str(contract, "currency")}/${str(contract, "unit")}` : "—"} />
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-2 text-tertiary">
                <FolderKanban size={36} strokeWidth={1.2} /><span className="text-sm">Select a project</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-hidden">
          <KanbanBoard entities={boardFiltered} columns={PROJECT_COLUMNS}
            columnFor={(e) => stageStore.columnFor(e)} onMove={moveToColumn}
            renderCard={(proj, col) => <ProjectCard project={proj} color={col.color} />} />
        </div>
      )}
    </div>
  );
}

function clientName(p: Entity): string {
  const c = entity(p, "contract");
  return c ? str(entity(c, "client") || ({} as Entity), "name") : "";
}

function ProjectCard({ project }: { project: Entity; color: string }) {
  const cName = clientName(project);
  const c = entity(project, "contract");
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold truncate">{str(project, "title")}</span>
        {str(project, "tag") && (
          <span className="text-xs font-medium px-1.5 py-0.5 rounded bg-bg-hover text-secondary shrink-0">
            {str(project, "tag")}
          </span>
        )}
      </div>
      {cName && (
        <div className="flex items-center gap-1 text-secondary">
          <Building2 size={12} className="text-tertiary" />
          <span className="text-xs truncate">{cName}</span>
        </div>
      )}
      {c && str(c, "title") && (
        <div className="flex items-center gap-1 text-secondary">
          <FileSignature size={12} className="text-tertiary" />
          <span className="text-xs truncate">{str(c, "title")}</span>
        </div>
      )}
      <div className="flex items-center justify-between text-tertiary">
        {dateRange(project) && (
          <div className="flex items-center gap-1">
            <Calendar size={12} /><span className="text-xs">{dateRange(project)}</span>
          </div>
        )}
        <div className="flex items-center gap-2">
          {int(project, "num_invoices") > 0 && (
            <div className="flex items-center gap-0.5"><FileText size={12} /><span className="text-xs">{int(project, "num_invoices")}</span></div>
          )}
          {int(project, "num_timesheets") > 0 && (
            <div className="flex items-center gap-0.5"><Clock size={12} /><span className="text-xs">{int(project, "num_timesheets")}</span></div>
          )}
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wider text-tertiary mb-0.5">{label}</div>
      <div className="text-sm">{value}</div>
    </div>
  );
}
