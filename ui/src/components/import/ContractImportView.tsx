import { useEffect, useState, useRef, useCallback } from "react";
import {
  FileUp, Sparkles, Loader2, X, Check, CheckCheck,
  Trash2, ChevronDown, ChevronRight, Link2, AlertTriangle,
  Users, Building2, FileSignature, FolderKanban, Circle,
  XCircle,
} from "lucide-react";
import { rpc } from "../../api/rpc";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AddressData {
  street: string; number: string; city: string;
  postal_code: string; country: string;
}

interface ParsedContact {
  ref: string; first_name: string; last_name: string;
  company: string; email: string; address: AddressData | null;
}

interface ParsedClient {
  ref: string; name: string; contact_ref: string;
}

interface ParsedContract {
  ref: string; title: string; client_ref: string;
  rate: number | null; currency: string; unit: string;
  billing_cycle: string; volume: number | null;
  signature_date: string; start_date: string; end_date: string;
  VAT_rate: number | null; term_of_payment: number | null;
}

interface ParsedProject {
  ref: string; title: string; tag: string; description: string;
  start_date: string; end_date: string; contract_ref: string;
}

type EntityStatus = "accepted" | "discarded";

interface ImportEntity<T> {
  data: T;
  status: EntityStatus;
  matchedExistingId?: number;
  existingData?: Record<string, unknown>;
  updateExisting?: boolean;
}

interface ExistingEntity {
  id: number;
  [key: string]: unknown;
}

interface ExistingEntities {
  contacts: ExistingEntity[];
  clients: ExistingEntity[];
  contracts: ExistingEntity[];
  projects: ExistingEntity[];
}

type StepStatus = "pending" | "running" | "done" | "error";

interface ImportStep {
  key: string;
  label: string;
  status: StepStatus;
  error: string | null;
}

interface ExtractionResult {
  steps: ImportStep[];
  contacts?: ParsedContact[];
  clients?: ParsedClient[];
  contracts?: ParsedContract[];
  projects?: ParsedProject[];
}

type Phase = "upload" | "review" | "committed";

const PIPELINE_STEPS: Omit<ImportStep, "status" | "error">[] = [
  { key: "load_config", label: "Loading LLM configuration" },
  { key: "read_document", label: "Reading document" },
  { key: "connect_llm", label: "Connecting to LLM" },
  { key: "summarize_document", label: "Analysing document" },
  { key: "extract_entities", label: "Extracting structured entities" },
  { key: "map_results", label: "Processing results" },
];

function makeSteps(upTo: number, running: number): ImportStep[] {
  return PIPELINE_STEPS.map((s, i) => ({
    ...s,
    status: i < upTo ? "done" : i === running ? "running" : "pending",
    error: null,
  }));
}

// ---------------------------------------------------------------------------
// Main View
// ---------------------------------------------------------------------------

export function ContractImportView() {
  const [phase, setPhase] = useState<Phase>("upload");
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [importSteps, setImportSteps] = useState<ImportStep[]>([]);

  const [contacts, setContacts] = useState<ImportEntity<ParsedContact>[]>([]);
  const [clients, setClients] = useState<ImportEntity<ParsedClient>[]>([]);
  const [contracts, setContracts] = useState<ImportEntity<ParsedContract>[]>([]);
  const [projects, setProjects] = useState<ImportEntity<ParsedProject>[]>([]);

  const [existing, setExisting] = useState<ExistingEntities | null>(null);
  const [commitResult, setCommitResult] = useState<Record<string, string[]> | null>(null);
  const [commitError, setCommitError] = useState<string | null>(null);
  const [committing, setCommitting] = useState(false);

  useEffect(() => {
    rpc<ExistingEntities>("imports.get_existing_entities").then((res) => {
      if (res.ok && res.data) setExisting(res.data);
    });
  }, []);

  async function handleFile(file: File) {
    setParsing(true);
    setParseError(null);

    // Optimistic client-side step progression while the synchronous RPC runs.
    // Steps 0-2 (config, read, connect) are sub-second;
    // step 3 (summarize) and step 4 (extract) are the two LLM passes.
    setImportSteps(makeSteps(0, 0));
    const t1 = setTimeout(() => setImportSteps(makeSteps(1, 1)), 300);
    const t2 = setTimeout(() => setImportSteps(makeSteps(2, 2)), 600);
    const t3 = setTimeout(() => setImportSteps(makeSteps(3, 3)), 1000);

    try {
      const buffer = await file.arrayBuffer();
      const base64 = btoa(
        new Uint8Array(buffer).reduce((d, b) => d + String.fromCharCode(b), "")
      );
      const res = await rpc<ExtractionResult>("llm.parse_contract_document", {
        file_base64: base64, file_name: file.name,
      });

      clearTimeout(t1); clearTimeout(t2); clearTimeout(t3);
      const data = res.data ?? (res as unknown as { data: ExtractionResult }).data;
      if (data?.steps) setImportSteps(data.steps);

      if (res.ok && data?.contacts) {
        const ex = existing;
        setContacts(data.contacts.map((c) => autoMatch(c, ex?.contacts, "first_name", "last_name")));
        setClients((data.clients ?? []).map((c) => autoMatch(c, ex?.clients, "name")));
        setContracts((data.contracts ?? []).map((c) => autoMatch(c, ex?.contracts, "title")));
        setProjects((data.projects ?? []).map((c) => autoMatch(c, ex?.projects, "title")));
        setPhase("review");
      } else {
        const failedStep = data?.steps?.find((s: ImportStep) => s.status === "error");
        setParseError(failedStep?.error || res.error || "Failed to parse document.");
      }
    } catch (err) {
      clearTimeout(t1); clearTimeout(t2); clearTimeout(t3);
      setParseError(String(err));
    }
    setParsing(false);
  }

  function startOver() {
    setPhase("upload");
    setContacts([]); setClients([]); setContracts([]); setProjects([]);
    setCommitResult(null); setCommitError(null);
    setImportSteps([]); setParseError(null);
  }

  async function handleCommit() {
    setCommitting(true);
    setCommitError(null);

    const payload = {
      contacts: accepted(contacts).map((e) => commitShape(e)),
      clients: accepted(clients).map((e) => commitShape(e)),
      contracts: accepted(contracts).map((e) => commitShape(e)),
      projects: accepted(projects).map((e) => commitShape(e)),
    };

    const res = await rpc<Record<string, string[]>>("imports.commit_contract_import", { data: payload });
    setCommitting(false);
    if (res.ok && res.data) {
      setCommitResult(res.data);
      setPhase("committed");
    } else {
      setCommitError(res.error || "Commit failed.");
    }
  }

  const totalAccepted = accepted(contacts).length + accepted(clients).length
    + accepted(contracts).length + accepted(projects).length;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-2 shrink-0 border-b border-border-subtle">
        <Sparkles size={16} className="text-fuchsia-400" />
        <h2 className="text-sm font-semibold">Contract Import</h2>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {phase === "upload" && (
          <UploadPhase
            parsing={parsing}
            parseError={parseError}
            importSteps={importSteps}
            onFileSelected={handleFile}
          />
        )}

        {phase === "review" && (
          <div className="space-y-6 max-w-4xl">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Review Extracted Entities</h2>
              <div className="flex items-center gap-2">
                <button onClick={startOver}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-secondary hover:text-primary hover:bg-bg-hover transition-colors">
                  <X size={14} /> Start Over
                </button>
                <button
                  onClick={handleCommit}
                  disabled={totalAccepted === 0 || committing}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium text-fuchsia-400 hover:bg-fuchsia-500/10 border border-fuchsia-400/30 transition-colors disabled:opacity-40"
                >
                  {committing ? <Loader2 size={14} className="animate-spin" /> : <CheckCheck size={14} />}
                  {committing ? "Committing..." : `Commit ${totalAccepted} Entities`}
                </button>
              </div>
            </div>

            {commitError && (
              <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
                {commitError}
              </div>
            )}

            <EntitySection<ParsedContact>
              icon={<Users size={16} />}
              title="Contacts"
              items={contacts}
              setItems={setContacts}
              existing={existing?.contacts || []}
              matchFields={["first_name", "last_name"]}
              renderCard={(item, idx, update) => (
                <ContactCard item={item} onUpdate={(u) => update(idx, u)} existing={existing?.contacts || []} />
              )}
            />

            <EntitySection<ParsedClient>
              icon={<Building2 size={16} />}
              title="Clients"
              items={clients}
              setItems={setClients}
              existing={existing?.clients || []}
              matchFields={["name"]}
              renderCard={(item, idx, update) => (
                <ClientCard
                  item={item} onUpdate={(u) => update(idx, u)}
                  existing={existing?.clients || []}
                  contacts={contacts}
                />
              )}
            />

            <EntitySection<ParsedContract>
              icon={<FileSignature size={16} />}
              title="Contracts"
              items={contracts}
              setItems={setContracts}
              existing={existing?.contracts || []}
              matchFields={["title"]}
              renderCard={(item, idx, update) => (
                <ContractCard
                  item={item} onUpdate={(u) => update(idx, u)}
                  existing={existing?.contracts || []}
                  clients={clients}
                />
              )}
            />

            <EntitySection<ParsedProject>
              icon={<FolderKanban size={16} />}
              title="Projects"
              items={projects}
              setItems={setProjects}
              existing={existing?.projects || []}
              matchFields={["title"]}
              renderCard={(item, idx, update) => (
                <ProjectCard
                  item={item} onUpdate={(u) => update(idx, u)}
                  existing={existing?.projects || []}
                  importedContracts={contracts}
                />
              )}
            />
          </div>
        )}

        {phase === "committed" && commitResult && (
          <CommittedPhase result={commitResult} onDone={startOver} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload Phase
// ---------------------------------------------------------------------------

const ACCEPT_EXTENSIONS = [".pdf", ".txt", ".md", ".text"];

function StepIcon({ status }: { status: StepStatus }) {
  switch (status) {
    case "done":
      return <Check size={14} className="text-emerald-400" />;
    case "running":
      return <Loader2 size={14} className="animate-spin text-fuchsia-400" />;
    case "error":
      return <XCircle size={14} className="text-red-400" />;
    default:
      return <Circle size={14} className="text-tertiary/40" />;
  }
}

function PipelineSteps({ steps, error }: { steps: ImportStep[]; error: string | null }) {
  const hasError = steps.some((s) => s.status === "error");

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        {steps.map((step) => (
          <div
            key={step.key}
            className={`flex items-start gap-3 px-3 py-2 rounded-lg transition-colors ${
              step.status === "running" ? "bg-fuchsia-500/5" :
              step.status === "error" ? "bg-red-500/5" :
              ""
            }`}
          >
            <div className="mt-0.5 shrink-0">
              <StepIcon status={step.status} />
            </div>
            <div className="min-w-0 flex-1">
              <p className={`text-sm ${
                step.status === "done" ? "text-secondary" :
                step.status === "running" ? "text-primary font-medium" :
                step.status === "error" ? "text-red-400 font-medium" :
                "text-tertiary"
              }`}>
                {step.label}
              </p>
              {step.status === "error" && step.error && (
                <p className="text-xs text-red-400/80 mt-1">{step.error}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      {hasError && error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
          {error}
        </div>
      )}
    </div>
  );
}

function UploadPhase({ parsing, parseError, importSteps, onFileSelected }: {
  parsing: boolean; parseError: string | null;
  importSteps: ImportStep[];
  onFileSelected: (f: File) => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasSteps = importSteps.length > 0;
  const hasError = importSteps.some((s) => s.status === "error");

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file && ACCEPT_EXTENSIONS.some((ext) => file.name.toLowerCase().endsWith(ext)))
      onFileSelected(file);
  }, [onFileSelected]);

  return (
    <div className="max-w-xl mx-auto mt-12 space-y-5">
      <div className="text-center space-y-2">
        <h2 className="text-xl font-semibold">Import a Contract Document</h2>
        <p className="text-sm text-secondary">
          Upload a contract document and AI will extract contacts, clients,
          contracts, and projects from it.
        </p>
      </div>

      {!parsing && !hasSteps && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`flex flex-col items-center justify-center gap-3 p-10 rounded-xl border-2 border-dashed cursor-pointer transition-colors
            ${dragOver ? "border-fuchsia-400 bg-fuchsia-500/5" : "border-border-subtle hover:border-fuchsia-400/50 hover:bg-fuchsia-500/5"}`}
        >
          <FileUp size={32} strokeWidth={1.4} className="text-fuchsia-400" />
          <div className="text-center">
            <p className="text-sm font-medium">Drop a document here</p>
            <p className="text-xs text-tertiary mt-1">PDF, TXT, or Markdown</p>
          </div>
          <input ref={inputRef} type="file" className="hidden"
            accept=".pdf,.txt,.md,.text" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFileSelected(f); }} />
        </div>
      )}

      {(parsing || hasSteps) && (
        <div className="rounded-xl border border-border-subtle bg-bg-card p-5">
          {hasSteps ? (
            <PipelineSteps steps={importSteps} error={parseError} />
          ) : (
            <div className="flex items-center justify-center gap-3 py-6">
              <Loader2 size={20} className="animate-spin text-fuchsia-400" />
              <span className="text-sm text-secondary">Preparing...</span>
            </div>
          )}
        </div>
      )}

      {!hasSteps && parseError && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
          {parseError}
        </div>
      )}

      {hasError && (
        <label className="flex items-center gap-2 mx-auto px-4 py-2 rounded-lg text-sm font-medium text-fuchsia-400 hover:bg-fuchsia-500/10 border border-fuchsia-400/30 transition-colors cursor-pointer">
          <FileUp size={14} /> Try Again
          <input type="file" className="hidden"
            accept=".pdf,.txt,.md,.text" onChange={(e) => { const f = e.target.files?.[0]; if (f) onFileSelected(f); }} />
        </label>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Committed Phase
// ---------------------------------------------------------------------------

function CommittedPhase({ result, onDone }: {
  result: Record<string, string[]>; onDone: () => void;
}) {
  const created = result.created || [];
  const linked = result.linked || [];
  const updated = result.updated || [];
  const total = created.length + linked.length + updated.length;

  return (
    <div className="max-w-xl mx-auto mt-12 space-y-5 text-center">
      <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto">
        <Check size={32} className="text-emerald-400" />
      </div>
      <h2 className="text-xl font-semibold">Import Complete</h2>
      <p className="text-sm text-secondary">{total} entities processed.</p>

      <div className="text-left space-y-2 bg-bg-card rounded-lg border border-border-subtle p-4">
        {created.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-emerald-400 mb-1">Created</div>
            {created.map((s, i) => <div key={i} className="text-sm text-secondary">{s}</div>)}
          </div>
        )}
        {linked.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-blue-400 mb-1">Linked to existing</div>
            {linked.map((s, i) => <div key={i} className="text-sm text-secondary">{s}</div>)}
          </div>
        )}
        {updated.length > 0 && (
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-amber-400 mb-1">Updated</div>
            {updated.map((s, i) => <div key={i} className="text-sm text-secondary">{s}</div>)}
          </div>
        )}
      </div>

      <button onClick={onDone}
        className="px-5 py-2 rounded-lg bg-bg-card text-primary text-sm font-medium border border-border-subtle hover:bg-bg-hover transition-colors">
        Done
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generic Entity Section
// ---------------------------------------------------------------------------

function EntitySection<T extends { ref: string }>({ icon, title, items, setItems, existing, matchFields, renderCard }: {
  icon: React.ReactNode;
  title: string;
  items: ImportEntity<T>[];
  setItems: React.Dispatch<React.SetStateAction<ImportEntity<T>[]>>;
  existing: ExistingEntity[];
  matchFields: string[];
  renderCard: (item: ImportEntity<T>, idx: number, update: (idx: number, item: ImportEntity<T>) => void) => React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  if (items.length === 0) return null;

  const acceptedCount = items.filter((i) => i.status === "accepted").length;

  function update(idx: number, item: ImportEntity<T>) {
    setItems((prev) => prev.map((p, i) => i === idx ? item : p));
  }

  function toggleStatus(idx: number) {
    setItems((prev) => prev.map((p, i) =>
      i === idx ? { ...p, status: p.status === "accepted" ? "discarded" : "accepted" } : p
    ));
  }

  function acceptAll() {
    setItems((prev) => prev.map((p) => ({ ...p, status: "accepted" })));
  }

  return (
    <div>
      <div onClick={() => setCollapsed((c) => !c)}
        className="flex items-center gap-2 w-full py-2 text-left group cursor-pointer" role="button">
        {collapsed ? <ChevronRight size={14} className="text-tertiary" /> : <ChevronDown size={14} className="text-tertiary" />}
        <span className="text-tertiary">{icon}</span>
        <span className="text-sm font-semibold">{title}</span>
        <span className="text-xs text-fuchsia-400 font-medium">
          {acceptedCount}/{items.length}
        </span>
        {acceptedCount < items.length && (
          <button
            onClick={(e) => { e.stopPropagation(); acceptAll(); }}
            className="ml-auto text-xs text-fuchsia-400 hover:text-fuchsia-300 transition-colors"
          >
            Accept All
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="space-y-3 ml-6">
          {items.map((item, idx) => (
            <div key={item.data.ref} className={`rounded-xl border-2 p-4 transition-all ${
              item.status === "discarded"
                ? "border-border-subtle opacity-50"
                : "border-fuchsia-400/40 bg-fuchsia-500/5"
            }`}>
              <div className="flex items-center justify-between mb-3">
                <MatchBadge item={item} existing={existing}
                  onChangeMatch={(id) => update(idx, {
                    ...item,
                    matchedExistingId: id || undefined,
                    existingData: id ? existing.find((e) => e.id === id) : undefined,
                  })}
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => toggleStatus(idx)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                      item.status === "discarded"
                        ? "text-fuchsia-400 hover:bg-fuchsia-500/10"
                        : "text-secondary hover:text-red-400 hover:bg-red-500/10"
                    }`}
                  >
                    {item.status === "discarded" ? <><Check size={12} /> Restore</> : <><Trash2 size={12} /> Discard</>}
                  </button>
                </div>
              </div>
              {item.status === "accepted" && renderCard(item, idx, update)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match Badge + Dropdown
// ---------------------------------------------------------------------------

function MatchBadge<T extends { ref: string }>({ item, existing, onChangeMatch }: {
  item: ImportEntity<T>;
  existing: ExistingEntity[];
  onChangeMatch: (id: number | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const matched = item.matchedExistingId;
  const matchedEntity = matched ? existing.find((e) => e.id === matched) : null;
  const matchLabel = matchedEntity
    ? (matchedEntity.name || matchedEntity.title || `${matchedEntity.first_name} ${matchedEntity.last_name}` || `#${matchedEntity.id}`) as string
    : null;

  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors ${
          matched
            ? "text-blue-400 bg-blue-500/10 border border-blue-400/30"
            : "text-fuchsia-400 bg-fuchsia-500/10 border border-fuchsia-400/30"
        }`}
      >
        {matched ? <><Link2 size={11} /> Update: {matchLabel}</> : <><Sparkles size={11} /> Will create</>}
        <ChevronDown size={11} />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-bg-sidebar border border-border-subtle rounded-lg shadow-lg py-1 min-w-[200px] max-h-48 overflow-y-auto">
          <button onClick={() => { onChangeMatch(null); setOpen(false); }}
            className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${!matched ? "text-fuchsia-400 font-medium" : "text-secondary hover:bg-bg-hover"}`}>
            Create as new record
          </button>
          {existing.map((e) => {
            const label = (e.name || e.title || `${e.first_name || ""} ${e.last_name || ""}`.trim() || `#${e.id}`) as string;
            return (
              <button key={e.id} onClick={() => { onChangeMatch(e.id); setOpen(false); }}
                className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                  matched === e.id ? "text-blue-400 font-medium" : "text-secondary hover:bg-bg-hover"
                }`}>
                {label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Entity Cards
// ---------------------------------------------------------------------------

function ContactCard({ item, onUpdate, existing }: {
  item: ImportEntity<ParsedContact>;
  onUpdate: (u: ImportEntity<ParsedContact>) => void;
  existing: ExistingEntity[];
}) {
  const d = item.data;
  const ex = item.existingData;
  const addr = d.address ?? { street: "", number: "", city: "", postal_code: "", country: "" };

  function set(field: keyof ParsedContact, value: string) {
    onUpdate({ ...item, data: { ...d, [field]: value } });
  }
  function setAddr(field: string, value: string) {
    onUpdate({ ...item, data: { ...d, address: { ...addr, [field]: value } } });
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <AiField label="First Name" value={d.first_name} dbValue={ex?.first_name as string} onChange={(v) => set("first_name", v)} />
        <AiField label="Last Name" value={d.last_name} dbValue={ex?.last_name as string} onChange={(v) => set("last_name", v)} />
        <AiField label="Company" value={d.company} dbValue={ex?.company as string} onChange={(v) => set("company", v)} />
        <AiField label="Email" value={d.email} dbValue={ex?.email as string} onChange={(v) => set("email", v)} />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <AiField label="Street" value={addr.street} onChange={(v) => setAddr("street", v)} />
        <AiField label="Number" value={addr.number} onChange={(v) => setAddr("number", v)} />
        <AiField label="City" value={addr.city} onChange={(v) => setAddr("city", v)} />
        <AiField label="Postal Code" value={addr.postal_code} onChange={(v) => setAddr("postal_code", v)} />
        <AiField label="Country" value={addr.country} onChange={(v) => setAddr("country", v)} />
      </div>
    </div>
  );
}

function ClientCard({ item, onUpdate, existing, contacts }: {
  item: ImportEntity<ParsedClient>;
  onUpdate: (u: ImportEntity<ParsedClient>) => void;
  existing: ExistingEntity[];
  contacts: ImportEntity<ParsedContact>[];
}) {
  const d = item.data;
  const ex = item.existingData;
  const acceptedContacts = contacts.filter((c) => c.status === "accepted");

  function set(field: keyof ParsedClient, value: string) {
    onUpdate({ ...item, data: { ...d, [field]: value } });
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <AiField label="Name" value={d.name} dbValue={ex?.name as string} onChange={(v) => set("name", v)} />
      </div>
      <RefDropdown
        label="Invoicing Contact"
        currentRef={d.contact_ref}
        options={acceptedContacts.map((c) => ({
          ref: c.data.ref,
          label: `${c.data.first_name} ${c.data.last_name}`.trim() || c.data.company || c.data.ref,
        }))}
        onChange={(ref) => set("contact_ref", ref)}
        hint={d.contact_ref}
      />
    </div>
  );
}

function ContractCard({ item, onUpdate, existing, clients }: {
  item: ImportEntity<ParsedContract>;
  onUpdate: (u: ImportEntity<ParsedContract>) => void;
  existing: ExistingEntity[];
  clients: ImportEntity<ParsedClient>[];
}) {
  const d = item.data;
  const ex = item.existingData;
  const acceptedClients = clients.filter((c) => c.status === "accepted");

  function set<K extends keyof ParsedContract>(field: K, value: ParsedContract[K]) {
    onUpdate({ ...item, data: { ...d, [field]: value } });
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-2">
        <AiField label="Title" value={d.title} dbValue={ex?.title as string} onChange={(v) => set("title", v)} />
        <AiField label="Rate" value={String(d.rate ?? "")} onChange={(v) => set("rate", v ? parseFloat(v) : null)} />
        <AiField label="Currency" value={d.currency} onChange={(v) => set("currency", v)} />
        <AiField label="Unit" value={d.unit} onChange={(v) => set("unit", v)} />
        <AiField label="Billing Cycle" value={d.billing_cycle} onChange={(v) => set("billing_cycle", v)} />
        <AiField label="Volume" value={String(d.volume ?? "")} onChange={(v) => set("volume", v ? parseInt(v) : null)} />
      </div>
      <div className="grid grid-cols-3 gap-2">
        <AiField label="Signature Date" value={d.signature_date} onChange={(v) => set("signature_date", v)} type="date" />
        <AiField label="Start Date" value={d.start_date} onChange={(v) => set("start_date", v)} type="date" />
        <AiField label="End Date" value={d.end_date} onChange={(v) => set("end_date", v)} type="date" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <AiField label="VAT Rate" value={String(d.VAT_rate ?? "")} onChange={(v) => set("VAT_rate", v ? parseFloat(v) : null)} />
        <AiField label="Term of Payment (days)" value={String(d.term_of_payment ?? "")} onChange={(v) => set("term_of_payment", v ? parseInt(v) : null)} />
      </div>
      <RefDropdown
        label="Client"
        currentRef={d.client_ref}
        options={acceptedClients.map((c) => ({
          ref: c.data.ref,
          label: c.data.name || c.data.ref,
        }))}
        onChange={(ref) => set("client_ref", ref)}
        hint={d.client_ref}
      />
    </div>
  );
}

function ProjectCard({ item, onUpdate, existing, importedContracts }: {
  item: ImportEntity<ParsedProject>;
  onUpdate: (u: ImportEntity<ParsedProject>) => void;
  existing: ExistingEntity[];
  importedContracts: ImportEntity<ParsedContract>[];
}) {
  const d = item.data;
  const ex = item.existingData;
  const acceptedContracts = importedContracts.filter((c) => c.status === "accepted");

  function set<K extends keyof ParsedProject>(field: K, value: ParsedProject[K]) {
    onUpdate({ ...item, data: { ...d, [field]: value } });
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <AiField label="Title" value={d.title} dbValue={ex?.title as string} onChange={(v) => set("title", v)} />
        <AiField label="Tag" value={d.tag} onChange={(v) => set("tag", v)} />
      </div>
      <AiField label="Description" value={d.description} onChange={(v) => set("description", v)} />
      <div className="grid grid-cols-2 gap-2">
        <AiField label="Start Date" value={d.start_date} onChange={(v) => set("start_date", v)} type="date" />
        <AiField label="End Date" value={d.end_date} onChange={(v) => set("end_date", v)} type="date" />
      </div>
      <RefDropdown
        label="Contract"
        currentRef={d.contract_ref}
        options={acceptedContracts.map((c) => ({
          ref: c.data.ref,
          label: c.data.title || c.data.ref,
        }))}
        onChange={(ref) => set("contract_ref", ref)}
        hint={d.contract_ref}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared UI primitives
// ---------------------------------------------------------------------------

function AiField({ label, value, dbValue, onChange, type = "text" }: {
  label: string; value: string | null | undefined; dbValue?: string;
  onChange: (v: string) => void; type?: string;
}) {
  const safeValue = value ?? "";
  const differs = dbValue != null && dbValue !== "" && safeValue !== dbValue;

  return (
    <div>
      <label className="block text-xs text-fuchsia-300/70 mb-0.5">{label}</label>
      <input type={type} value={safeValue} onChange={(e) => onChange(e.target.value)}
        className={`w-full px-2.5 py-1.5 rounded-md text-sm bg-bg-card text-primary outline-none
          focus:border-fuchsia-400 transition-colors placeholder:text-muted border ${
          differs ? "border-amber-400/60" : "border-fuchsia-400/30"
        }`} />
      {differs && (
        <div className="text-[10px] text-amber-400/80 mt-0.5 truncate" title={`DB: ${dbValue}`}>
          DB: {dbValue}
        </div>
      )}
    </div>
  );
}

function RefDropdown({ label, currentRef, options, onChange, hint }: {
  label: string;
  currentRef: string | null | undefined;
  options: { ref: string; label: string }[];
  onChange: (ref: string) => void;
  hint?: string;
}) {
  const safeRef = currentRef ?? "";
  const noLink = !safeRef || !options.some((o) => o.ref === safeRef);

  return (
    <div>
      <label className="block text-xs text-fuchsia-300/70 mb-0.5">
        {label}
        {noLink && options.length > 0 && (
          <span className="ml-1.5 text-amber-400">
            <AlertTriangle size={10} className="inline -mt-0.5" /> not linked
          </span>
        )}
      </label>
      <select
        value={safeRef}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2.5 py-1.5 rounded-md text-sm bg-bg-card text-primary border border-fuchsia-400/30 outline-none focus:border-fuchsia-400 transition-colors"
      >
        <option value="">-- Select --</option>
        {options.map((o) => (
          <option key={o.ref} value={o.ref}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function autoMatch<T extends { ref: string }>(
  data: T,
  existingList: ExistingEntity[] | undefined,
  ...matchKeys: string[]
): ImportEntity<T> {
  const entity: ImportEntity<T> = { data, status: "accepted" };
  if (!existingList) return entity;

  for (const ex of existingList) {
    const d = data as unknown as Record<string, unknown>;
    const matches = matchKeys.every((k) => {
      const a = String(d[k] || "").toLowerCase().trim();
      const b = String(ex[k] || "").toLowerCase().trim();
      return a && b && a === b;
    });
    if (matches) {
      entity.matchedExistingId = ex.id;
      entity.existingData = ex as Record<string, unknown>;
      break;
    }
  }
  return entity;
}

function accepted<T>(items: ImportEntity<T>[]): ImportEntity<T>[] {
  return items.filter((i) => i.status === "accepted");
}

function commitShape<T extends { ref: string }>(item: ImportEntity<T>): Record<string, unknown> {
  const d: Record<string, unknown> = { ...item.data };
  if (item.matchedExistingId) {
    d.existing_id = item.matchedExistingId;
    d.update_existing = true;
  }
  return d;
}
