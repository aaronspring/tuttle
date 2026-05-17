import { useEffect, useState, useCallback } from "react";
import {
  FileText, Send, CheckCircle, XCircle, Mail,
  Building2, FolderKanban, Calendar, Banknote, Eye, Search,
  Plus, Clock,
} from "lucide-react";
import { rpc, readFileAsDataURL } from "../../api/rpc";
import { str, num, bool, list as entityList, formatDate, invoiceStatus, deepStr } from "../../api/entity";
import { StatusBadge } from "../shared/StatusBadge";
import { ViewModeToggle } from "../shared/ViewModeToggle";
import { KanbanBoard, useStageStore, type BoardColumn } from "../shared/KanbanBoard";
import { useNavigation } from "../shared/NavigationContext";
import type { Entity } from "../../api/types";

const INVOICE_COLUMNS: BoardColumn[] = [
  { id: "Draft", label: "Draft", color: "#8e8e93" },
  { id: "Sent", label: "Sent", color: "#3b82f6" },
  { id: "Paid", label: "Paid", color: "#22c55e" },
  { id: "Overdue", label: "Overdue", color: "#ef4444" },
  { id: "Cancelled", label: "Cancelled", color: "#f97316" },
];

const STATUS_FILTERS = ["All", "Draft", "Sent", "Paid", "Overdue", "Cancelled"] as const;
type StatusFilter = (typeof STATUS_FILTERS)[number];

const FILTER_COLORS: Record<string, string> = {
  All: "#007AFF", Draft: "#a0a0a0", Sent: "#60a5fa",
  Paid: "#34d399", Overdue: "#f87171", Cancelled: "#fb923c",
};

export function InvoicingView() {
  const { filter: navFilter } = useNavigation();
  const [invoices, setInvoices] = useState<Entity[]>([]);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"list" | "board">("list");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [newlyCreatedId, setNewlyCreatedId] = useState<number | null>(null);

  const defaultColumn = useCallback(
    (e: { id: number; [k: string]: unknown }) => invoiceStatus(e as Entity), [],
  );
  const stageStore = useStageStore("invoice", INVOICE_COLUMNS, defaultColumn);

  useEffect(() => { load(); }, []);

  async function load(selectId?: number) {
    setLoading(true);
    const res = await rpc<Entity[]>("invoicing.get_all");
    if (res.ok && res.data) {
      const sorted = [...res.data].sort((a, b) => {
        const na = str(a, "number") || "";
        const nb = str(b, "number") || "";
        return nb.localeCompare(na);
      });
      setInvoices(sorted);
      const refreshId = selectId ?? selected?.id;
      if (refreshId != null) {
        const match = res.data.find((i) => i.id === refreshId);
        setSelected(match ?? null);
      }
    }
    setLoading(false);
  }

  function matchesSearch(inv: Entity) {
    if (!search) return true;
    const q = search.toLowerCase();
    return str(inv, "number").toLowerCase().includes(q)
      || deepStr(inv, "contract.client.name").toLowerCase().includes(q)
      || deepStr(inv, "project.title").toLowerCase().includes(q);
  }

  const filtered = invoices.filter((inv) =>
    (statusFilter === "All" || invoiceStatus(inv) === statusFilter) && matchesSearch(inv));
  const boardFiltered = invoices.filter(matchesSearch);

  async function toggleSent(id: number) { await rpc("invoicing.toggle_sent", { id }); load(); }
  async function togglePaid(id: number) { await rpc("invoicing.toggle_paid", { id }); load(); }
  async function toggleCancelled(id: number) { await rpc("invoicing.toggle_cancelled", { id }); load(); }
  async function sendMail(id: number) {
    const res = await rpc<void>("invoicing.send_mail", { id });
    if (!res.ok) alert(res.error || "Failed to send invoice");
  }

  async function moveToColumn(id: number, colId: string) {
    const inv = invoices.find((i) => i.id === id);
    if (!inv) return;
    if (stageStore.columnFor(inv) === colId) return;
    stageStore.setColumn(id, colId);
    const isSent = bool(inv, "sent"), isPaid = bool(inv, "paid"), isCancelled = bool(inv, "cancelled");
    if (colId === "Draft") { if (isSent) await toggleSent(id); if (isPaid) await togglePaid(id); if (isCancelled) await toggleCancelled(id); }
    else if (colId === "Sent") { if (isCancelled) await toggleCancelled(id); if (isPaid) await togglePaid(id); if (!isSent) await toggleSent(id); }
    else if (colId === "Paid") { if (isCancelled) await toggleCancelled(id); if (!isSent) await toggleSent(id); if (!isPaid) await togglePaid(id); }
    else if (colId === "Overdue") { if (isCancelled) await toggleCancelled(id); if (!isSent) await toggleSent(id); if (isPaid) await togglePaid(id); }
    else if (colId === "Cancelled") { if (!isCancelled) await toggleCancelled(id); }
    load();
  }

  if (loading && invoices.length === 0)
    return <div className="flex items-center justify-center h-full text-secondary">Loading invoices…</div>;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-2 px-4 py-2 shrink-0 border-b border-border-subtle">
        <h2 className="text-sm font-semibold">Invoicing</h2>
        <button onClick={() => setCreateOpen(true)}
          className="flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium bg-accent text-white hover:bg-accent/90 transition-colors">
          <Plus size={13} /> Create Invoice
        </button>
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
          {/* List */}
          <div className="w-[420px] shrink-0 flex flex-col overflow-hidden border-r border-border-subtle">
            <div className="flex-1 overflow-y-auto">
              {filtered.length === 0
                ? <div className="p-4 text-sm text-center text-tertiary">{search ? "No matches." : "No invoices."}</div>
                : filtered.map((inv) => {
                  const isSelected = selected?.id === inv.id;
                  const isHighlighted = !isSelected && (inv.id === newlyCreatedId || (navFilter.contractId != null && num(inv, "contract_id") === navFilter.contractId));
                  return <InvoiceRow key={inv.id} invoice={inv} isSelected={isSelected} isHighlighted={isHighlighted} onSelect={() => { setNewlyCreatedId(null); setSelected(inv); }} />;
                })}
            </div>
            <div className="px-4 py-2 text-xs text-tertiary border-t border-border-subtle">
              {filtered.length} invoice{filtered.length !== 1 ? "s" : ""}
            </div>
          </div>
          {/* Detail */}
          <div className="flex-1 overflow-y-auto">
            {selected ? (
              <InvoiceDetail invoice={selected} onToggleSent={() => toggleSent(selected.id)}
                onTogglePaid={() => togglePaid(selected.id)} onToggleCancelled={() => toggleCancelled(selected.id)}
                onSendMail={() => sendMail(selected.id)} />
            ) : (
              <div className="flex flex-col items-center justify-center h-full gap-2 text-tertiary">
                <FileText size={36} strokeWidth={1.2} /><span className="text-sm">Select an invoice</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="flex-1 overflow-hidden">
          <KanbanBoard entities={boardFiltered} columns={INVOICE_COLUMNS}
            columnFor={(e) => stageStore.columnFor(e)} onMove={moveToColumn}
            renderCard={(inv, col) => <InvoiceCard invoice={inv} color={col.color} />} />
        </div>
      )}

      {createOpen && (
        <CreateInvoiceDialog
          onClose={() => setCreateOpen(false)}
          onCreated={async (newId) => { setNewlyCreatedId(newId ?? null); await load(newId); setCreateOpen(false); }}
        />
      )}
    </div>
  );
}

function CreateInvoiceDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (newId?: number) => Promise<void> | void }) {
  const [projects, setProjects] = useState<Entity[]>([]);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().slice(0, 10));
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1); d.setDate(1); return d.toISOString().slice(0, 10);
  });
  const [toDate, setToDate] = useState(() => {
    const d = new Date(); d.setDate(0); return d.toISOString().slice(0, 10);
  });
  const [mode, setMode] = useState<"timetracking" | "manual">("timetracking");
  const [manualQty, setManualQty] = useState("");
  const [hasTimeData, setHasTimeData] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      const [projRes, ttRes] = await Promise.all([
        rpc<Entity[]>("projects.get_all"),
        rpc<{ total_events: number }>("timetracking.get_summary"),
      ]);
      if (projRes.ok && projRes.data) {
        const active = projRes.data.filter((p) => !bool(p, "is_completed"));
        setProjects(active);
        if (active.length > 0) setProjectId(active[0].id);
      }
      if (ttRes.ok && ttRes.data && ttRes.data.total_events > 0) setHasTimeData(true);
      else setMode("manual");
    })();
  }, []);

  async function submit() {
    if (!projectId) { setError("Select a project"); return; }
    setSubmitting(true);
    setError("");
    const params: Record<string, unknown> = {
      project_id: projectId,
      invoice_date: invoiceDate,
      from_date: fromDate,
      to_date: toDate,
    };
    if (mode === "manual") {
      const qty = parseFloat(manualQty);
      if (!qty || qty <= 0) { setError("Enter a valid quantity"); setSubmitting(false); return; }
      params.manual_quantity = qty;
    }
    const res = await rpc<{ id?: number }>("invoicing.create", params);
    if (res.ok) {
      await onCreated(res.data?.id);
    } else {
      setError(res.error || "Failed to create invoice");
    }
    setSubmitting(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-bg-content rounded-xl border border-border-subtle shadow-2xl w-[420px] max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-border-subtle">
          <h2 className="text-base font-semibold">Create Invoice</h2>
        </div>
        <div className="px-5 py-4 space-y-4">
          {/* Project */}
          <label className="block">
            <span className="text-xs font-semibold text-secondary uppercase tracking-wider">Project</span>
            <select value={projectId ?? ""} onChange={(e) => setProjectId(Number(e.target.value))}
              className="mt-1 w-full px-3 py-1.5 rounded-md bg-bg-card border border-border-subtle text-sm text-primary">
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{str(p, "title")}</option>
              ))}
            </select>
          </label>

          {/* Mode toggle */}
          <div>
            <span className="text-xs font-semibold text-secondary uppercase tracking-wider">Source</span>
            <div className="flex gap-2 mt-1">
              <button onClick={() => setMode("timetracking")} disabled={!hasTimeData}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-colors border
                  ${mode === "timetracking" ? "border-accent bg-accent/15 text-primary" : "border-border-subtle text-tertiary"}
                  ${!hasTimeData ? "opacity-40 cursor-not-allowed" : ""}`}>
                <Clock size={14} /> Time Tracking
              </button>
              <button onClick={() => setMode("manual")}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-colors border
                  ${mode === "manual" ? "border-accent bg-accent/15 text-primary" : "border-border-subtle text-tertiary"}`}>
                <FileText size={14} /> Manual
              </button>
            </div>
            {!hasTimeData && (
              <p className="text-[10px] text-muted mt-1">Import calendar data in Time Tracking to use this option.</p>
            )}
          </div>

          {/* Dates */}
          <div className="grid grid-cols-3 gap-2">
            <label className="block">
              <span className="text-[10px] font-semibold text-muted uppercase">Invoice Date</span>
              <input type="date" value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)}
                className="mt-1 w-full px-2 py-1.5 rounded-md bg-bg-card border border-border-subtle text-xs text-primary" />
            </label>
            <label className="block">
              <span className="text-[10px] font-semibold text-muted uppercase">From</span>
              <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
                className="mt-1 w-full px-2 py-1.5 rounded-md bg-bg-card border border-border-subtle text-xs text-primary" />
            </label>
            <label className="block">
              <span className="text-[10px] font-semibold text-muted uppercase">To</span>
              <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
                className="mt-1 w-full px-2 py-1.5 rounded-md bg-bg-card border border-border-subtle text-xs text-primary" />
            </label>
          </div>

          {/* Manual quantity */}
          {mode === "manual" && (
            <label className="block">
              <span className="text-xs font-semibold text-secondary uppercase tracking-wider">Quantity (hours)</span>
              <input type="number" min="0" step="0.5" value={manualQty} onChange={(e) => setManualQty(e.target.value)}
                placeholder="e.g. 40"
                className="mt-1 w-full px-3 py-1.5 rounded-md bg-bg-card border border-border-subtle text-sm text-primary placeholder:text-muted" />
            </label>
          )}

          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        <div className="px-5 py-3 border-t border-border-subtle flex justify-end gap-2">
          <button onClick={onClose}
            className="px-4 py-1.5 rounded-md text-sm text-secondary hover:text-primary hover:bg-bg-hover transition-colors">
            Cancel
          </button>
          <button onClick={submit} disabled={submitting}
            className="px-4 py-1.5 rounded-md text-sm font-medium bg-accent text-white hover:bg-accent/90 transition-colors disabled:opacity-50">
            {submitting ? "Creating…" : "Create Invoice"}
          </button>
        </div>
      </div>
    </div>
  );
}

function InvoiceRow({ invoice, isSelected, isHighlighted, onSelect }: { invoice: Entity; isSelected: boolean; isHighlighted?: boolean; onSelect: () => void }) {
  const status = invoiceStatus(invoice);
  return (
    <button onClick={onSelect}
      className={`w-full text-left px-4 py-3 border-b transition-colors
        ${isSelected ? "bg-bg-selected border-border-subtle" : isHighlighted ? "bg-accent/10 border-accent/30" : "border-border-subtle hover:bg-bg-hover"}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-medium">{str(invoice, "number") || "Draft"}</span>
          <span className="text-xs text-tertiary">{formatDate(str(invoice, "date"))}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <span className="text-sm font-semibold tabular-nums">{str(invoice, "total_formatted")}</span>
          <StatusBadge status={status} />
        </div>
      </div>
      <div className="flex items-center gap-1.5 mt-1 text-secondary">
        <span className="text-xs truncate">{deepStr(invoice, "contract.client.name") || "No client"}</span>
        {deepStr(invoice, "project.title") && (
          <><span className="text-tertiary">·</span>
          <span className="text-xs text-tertiary truncate">{deepStr(invoice, "project.title")}</span></>
        )}
      </div>
    </button>
  );
}

function InvoiceCard({ invoice }: { invoice: Entity; color: string }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{str(invoice, "number") || "Draft"}</span>
        <span className="text-sm font-bold tabular-nums">{str(invoice, "total_formatted")}</span>
      </div>
      {deepStr(invoice, "contract.client.name") && (
        <div className="flex items-center gap-1 text-secondary">
          <Building2 size={12} className="text-tertiary" />
          <span className="text-xs truncate">{deepStr(invoice, "contract.client.name")}</span>
        </div>
      )}
      {deepStr(invoice, "project.title") && (
        <div className="flex items-center gap-1 text-secondary">
          <FolderKanban size={12} className="text-tertiary" />
          <span className="text-xs truncate">{deepStr(invoice, "project.title")}</span>
        </div>
      )}
      <div className="flex items-center gap-1 text-tertiary">
        <Calendar size={12} /><span className="text-xs">{formatDate(str(invoice, "date"))}</span>
      </div>
    </div>
  );
}

function InvoiceDetail({ invoice, onToggleSent, onTogglePaid, onToggleCancelled, onSendMail }: {
  invoice: Entity; onToggleSent: () => void; onTogglePaid: () => void; onToggleCancelled: () => void; onSendMail: () => void;
}) {
  const status = invoiceStatus(invoice);
  const items = entityList(invoice, "items");
  const isCancelled = bool(invoice, "cancelled");
  const pdfPath = str(invoice, "pdf_path");

  const [detailTab, setDetailTab] = useState<"details" | "preview">(pdfPath ? "preview" : "details");
  const [pdfDataUrl, setPdfDataUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  useEffect(() => {
    setPdfDataUrl(null);
    if (pdfPath) {
      setDetailTab("preview");
      setPdfLoading(true);
      readFileAsDataURL(pdfPath, "application/pdf").then((url) => {
        setPdfDataUrl(url);
        setPdfLoading(false);
      });
    } else {
      setDetailTab("details");
    }
  }, [pdfPath, invoice.id]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-5 pb-3 space-y-3 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-bg-card flex items-center justify-center">
            <FileText size={18} className="text-secondary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">{str(invoice, "number") || "Draft"}</h1>
            <div className="flex items-center gap-2">
              <span className="text-sm text-secondary">{deepStr(invoice, "contract.client.name") || "No client"}</span>
              <StatusBadge status={status} />
            </div>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <AmountCard label="Subtotal" value={str(invoice, "sum_formatted")} />
          <AmountCard label="VAT" value={str(invoice, "vat_total_formatted")} color="#f97316" />
          <AmountCard label="Total" value={str(invoice, "total_formatted")} prominent />
        </div>

        {/* Tab switcher */}
        <div className="flex gap-1 border-b border-border-subtle">
          <TabBtn label="Preview" icon={<Eye size={14} />} active={detailTab === "preview"}
            disabled={!pdfPath} onClick={() => setDetailTab("preview")} />
          <TabBtn label="Details" icon={<FileText size={14} />} active={detailTab === "details"}
            onClick={() => setDetailTab("details")} />
        </div>
      </div>

      {/* Tab content */}
      {detailTab === "preview" ? (
        <div className="flex-1 min-h-0 px-5 pb-5">
          {pdfLoading ? (
            <div className="flex items-center justify-center h-full text-secondary">Loading PDF…</div>
          ) : pdfDataUrl ? (
            <embed src={pdfDataUrl} type="application/pdf"
              className="w-full h-full rounded-lg border border-border-subtle" />
          ) : (
            <div className="flex items-center justify-center h-full text-tertiary">
              PDF not available
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-5 pb-5 space-y-5">
          {items.length > 0 && (
            <Section title="Line Items">
              <div className="space-y-2">
                {items.map((item, i) => (
                  <div key={i} className="rounded-md p-3 bg-bg-card border border-border-subtle">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{str(item, "description")}</span>
                      <span className="text-sm font-semibold tabular-nums">{str(item, "subtotal_formatted")}</span>
                    </div>
                    <div className="flex items-center gap-3 mt-1.5 text-xs text-secondary">
                      <span>{num(item, "quantity").toFixed(1)} {str(item, "unit") || "hour"}</span>
                      <span>{str(item, "unit_price_formatted")}/{str(item, "unit") || "hour"}</span>
                      <span>{(num(item, "VAT_rate") * 100).toFixed(0)}% VAT</span>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          <Section title="Details">
            <div className="grid grid-cols-2 gap-3">
              <DRow icon={<Calendar size={14} />} label="Date" value={formatDate(str(invoice, "date"))} />
              <DRow icon={<FolderKanban size={14} />} label="Project" value={deepStr(invoice, "project.title") || "—"} />
              <DRow icon={<FileText size={14} />} label="Contract" value={deepStr(invoice, "contract.title") || "—"} />
              <DRow icon={<Banknote size={14} />} label="Currency" value={str(invoice, "currency") || "EUR"} />
            </div>
          </Section>

          <Section title="Actions">
            {!isCancelled && pdfPath && (
              <div className="mb-2">
                <button onClick={onSendMail}
                  className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition-colors bg-accent text-white hover:bg-accent/90">
                  <Mail size={16} /> Send Invoice
                </button>
              </div>
            )}
            <div className="flex gap-2">
              {!isCancelled && (
                <>
                  <ActionBtn label={bool(invoice, "sent") ? "Sent" : "Mark Sent"} icon={<Send size={16} />}
                    color="#3b82f6" active={bool(invoice, "sent")} onClick={onToggleSent} />
                  <ActionBtn label={bool(invoice, "paid") ? "Paid" : "Mark Paid"} icon={<CheckCircle size={16} />}
                    color="#22c55e" active={bool(invoice, "paid")} onClick={onTogglePaid} />
                </>
              )}
              <ActionBtn label={isCancelled ? "Restore" : "Cancel"} icon={<XCircle size={16} />}
                color="#f97316" active={isCancelled} onClick={onToggleCancelled} />
            </div>
          </Section>
        </div>
      )}
    </div>
  );
}

function TabBtn({ label, icon, active, disabled, onClick }: {
  label: string; icon: React.ReactNode; active: boolean; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button onClick={onClick} disabled={disabled}
      className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
        ${active ? "border-accent text-primary" : "border-transparent text-tertiary hover:text-secondary"}
        ${disabled ? "opacity-40 cursor-default" : ""}`}>
      {icon}{label}
    </button>
  );
}

function AmountCard({ label, value, color, prominent }: { label: string; value: string; color?: string; prominent?: boolean }) {
  return (
    <div className="text-center py-2.5 rounded-lg bg-bg-card border border-border-subtle"
      style={prominent ? { borderColor: `${color || "#007AFF"}44` } : undefined}>
      <div className="text-xs font-semibold uppercase tracking-wider text-tertiary mb-1">{label}</div>
      <div className={`tabular-nums ${prominent ? "text-base font-bold" : "text-sm font-medium"}`}
        style={prominent ? { color: color || "#007AFF" } : undefined}>{value || "—"}</div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div><div className="text-xs font-semibold uppercase tracking-wider text-secondary mb-2">{title}</div>{children}</div>;
}

function DRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-tertiary">{icon}</span>
      <div>
        <div className="text-xs font-semibold uppercase tracking-wider text-tertiary">{label}</div>
        <div className="text-sm">{value}</div>
      </div>
    </div>
  );
}

function ActionBtn({ label, icon, color, active, onClick }: {
  label: string; icon: React.ReactNode; color: string; active: boolean; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
      className="flex-1 flex flex-col items-center gap-1 py-2 rounded-lg text-sm font-medium transition-colors"
      style={{ background: active ? color : `${color}18`, color: active ? "#fff" : color }}>
      {icon}{label}
    </button>
  );
}
