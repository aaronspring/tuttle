import { useEffect, useState, useCallback } from "react";
import {
  FileText, Send, CheckCircle, XCircle,
  Building2, FolderKanban, Calendar, Banknote, Eye, Search,
} from "lucide-react";
import { rpc, readFileAsDataURL } from "../../api/rpc";
import { str, num, bool, list as entityList, formatDate, invoiceStatus } from "../../api/entity";
import { StatusBadge } from "../shared/StatusBadge";
import { ViewModeToggle } from "../shared/ViewModeToggle";
import { KanbanBoard, useStageStore, type BoardColumn } from "../shared/KanbanBoard";
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
  const [invoices, setInvoices] = useState<Entity[]>([]);
  const [selected, setSelected] = useState<Entity | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"list" | "board">("list");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [search, setSearch] = useState("");

  const defaultColumn = useCallback(
    (e: { id: number; [k: string]: unknown }) => invoiceStatus(e as Entity), [],
  );
  const stageStore = useStageStore("invoice", INVOICE_COLUMNS, defaultColumn);

  useEffect(() => { load(); }, []);

  async function load() {
    setLoading(true);
    const res = await rpc<Entity[]>("invoicing.get_all");
    if (res.ok && res.data) setInvoices(res.data);
    setLoading(false);
  }

  function matchesSearch(inv: Entity) {
    if (!search) return true;
    const q = search.toLowerCase();
    return str(inv, "number").toLowerCase().includes(q)
      || str(inv, "client_name").toLowerCase().includes(q)
      || str(inv, "project_title").toLowerCase().includes(q);
  }

  const filtered = invoices.filter((inv) =>
    (statusFilter === "All" || invoiceStatus(inv) === statusFilter) && matchesSearch(inv));
  const boardFiltered = invoices.filter(matchesSearch);

  async function toggleSent(id: number) { await rpc("invoicing.toggle_sent", { id }); load(); }
  async function togglePaid(id: number) { await rpc("invoicing.toggle_paid", { id }); load(); }
  async function toggleCancelled(id: number) { await rpc("invoicing.toggle_cancelled", { id }); load(); }

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
                : filtered.map((inv) => (
                  <InvoiceRow key={inv.id} invoice={inv} isSelected={selected?.id === inv.id} onSelect={() => setSelected(inv)} />
                ))}
            </div>
            <div className="px-4 py-2 text-xs text-tertiary border-t border-border-subtle">
              {filtered.length} invoice{filtered.length !== 1 ? "s" : ""}
            </div>
          </div>
          {/* Detail */}
          <div className="flex-1 overflow-y-auto">
            {selected ? (
              <InvoiceDetail invoice={selected} onToggleSent={() => toggleSent(selected.id)}
                onTogglePaid={() => togglePaid(selected.id)} onToggleCancelled={() => toggleCancelled(selected.id)} />
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
    </div>
  );
}

function InvoiceRow({ invoice, isSelected, onSelect }: { invoice: Entity; isSelected: boolean; onSelect: () => void }) {
  const status = invoiceStatus(invoice);
  return (
    <button onClick={onSelect}
      className={`w-full text-left px-4 py-3 border-b border-border-subtle transition-colors ${isSelected ? "bg-bg-selected" : "hover:bg-bg-hover"}`}>
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
        <span className="text-xs truncate">{str(invoice, "client_name") || "No client"}</span>
        {str(invoice, "project_title") && (
          <><span className="text-tertiary">·</span>
          <span className="text-xs text-tertiary truncate">{str(invoice, "project_title")}</span></>
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
      {str(invoice, "client_name") && (
        <div className="flex items-center gap-1 text-secondary">
          <Building2 size={12} className="text-tertiary" />
          <span className="text-xs truncate">{str(invoice, "client_name")}</span>
        </div>
      )}
      {str(invoice, "project_title") && (
        <div className="flex items-center gap-1 text-secondary">
          <FolderKanban size={12} className="text-tertiary" />
          <span className="text-xs truncate">{str(invoice, "project_title")}</span>
        </div>
      )}
      <div className="flex items-center gap-1 text-tertiary">
        <Calendar size={12} /><span className="text-xs">{formatDate(str(invoice, "date"))}</span>
      </div>
    </div>
  );
}

function InvoiceDetail({ invoice, onToggleSent, onTogglePaid, onToggleCancelled }: {
  invoice: Entity; onToggleSent: () => void; onTogglePaid: () => void; onToggleCancelled: () => void;
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
              <span className="text-sm text-secondary">{str(invoice, "client_name") || "No client"}</span>
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
              <DRow icon={<FolderKanban size={14} />} label="Project" value={str(invoice, "project_title") || "—"} />
              <DRow icon={<FileText size={14} />} label="Contract" value={str(invoice, "contract_title") || "—"} />
              <DRow icon={<Banknote size={14} />} label="Currency" value={str(invoice, "currency") || "EUR"} />
            </div>
          </Section>

          <Section title="Actions">
            <div className="flex gap-2">
              {!isCancelled && (
                <>
                  <ActionBtn label={bool(invoice, "sent") ? "Unsend" : "Mark Sent"} icon={<Send size={16} />}
                    color="#3b82f6" active={bool(invoice, "sent")} onClick={onToggleSent} />
                  <ActionBtn label={bool(invoice, "paid") ? "Unpay" : "Mark Paid"} icon={<CheckCircle size={16} />}
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
