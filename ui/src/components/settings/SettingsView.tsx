import { useEffect, useState } from "react";
import { Settings, RefreshCw, Save, CheckCircle2, AlertCircle, User, Bot, FileText, RotateCcw } from "lucide-react";
import { rpc } from "../../api/rpc";
import type { Entity } from "../../api/types";
import { str } from "../../api/entity";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LLMConfig {
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  request_timeout: number;
}

const DEFAULT_CONFIG: LLMConfig = {
  provider: "ollama",
  base_url: "http://localhost:11434",
  model: "",
  api_key: "",
  request_timeout: 600,
};

interface ProfileForm {
  name: string;
  subtitle: string;
  email: string;
  phone_number: string;
  website: string;
  VAT_number: string;
  operating_country: string;
  street: string;
  number: string;
  postal_code: string;
  city: string;
  country: string;
}

const EMPTY_PROFILE: ProfileForm = {
  name: "", subtitle: "", email: "", phone_number: "", website: "",
  VAT_number: "", operating_country: "Germany",
  street: "", number: "", postal_code: "", city: "", country: "Germany",
};

interface InvoicingPrefs {
  invoice_template: string;
  language: string;
  invoice_number_scheme: string;
}

const DEFAULT_INVOICING: InvoicingPrefs = {
  invoice_template: "invoice-modern",
  language: "en",
  invoice_number_scheme: "daily",
};

const SCHEME_EXAMPLES: Record<string, string> = {
  daily: "2025-05-17-01",
  yearly: "2025-01",
  plain: "01",
};

type Tab = "profile" | "invoicing" | "llm";

const TABS: { id: Tab; label: string; icon: typeof User }[] = [
  { id: "profile", label: "Profile", icon: User },
  { id: "invoicing", label: "Invoicing", icon: FileText },
  { id: "llm", label: "AI / LLM", icon: Bot },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SettingsView() {
  const [tab, setTab] = useState<Tab>("profile");

  const [config, setConfig] = useState<LLMConfig>(DEFAULT_CONFIG);
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  const [profile, setProfile] = useState<ProfileForm>({ ...EMPTY_PROFILE });
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileStatus, setProfileStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);
  const [isDemoUser, setIsDemoUser] = useState(false);
  const [resettingDemo, setResettingDemo] = useState(false);
  const [supportedCountries, setSupportedCountries] = useState<string[]>([]);

  const [invoicing, setInvoicing] = useState<InvoicingPrefs>({ ...DEFAULT_INVOICING });
  const [availableTemplates, setAvailableTemplates] = useState<Record<string, string>>({});
  const [availableLanguages, setAvailableLanguages] = useState<Record<string, string>>({});
  const [availableSchemes, setAvailableSchemes] = useState<Record<string, string>>({});
  const [invoicingSaving, setInvoicingSaving] = useState(false);
  const [invoicingStatus, setInvoicingStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => { loadConfig(); loadProfile(); loadInvoicingPrefs(); loadSupportedCountries(); }, []);

  // -- LLM config ----------------------------------------------------------

  async function loadConfig() {
    setLoading(true);
    const res = await rpc<LLMConfig>("llm.get_config");
    if (res.ok && res.data) {
      setConfig(res.data);
      if (res.data.base_url) await fetchModels(res.data.base_url);
    }
    setLoading(false);
  }

  async function fetchModels(baseUrl?: string) {
    const url = baseUrl || config.base_url;
    if (!url) return;
    setFetchingModels(true);
    setStatus(null);
    const res = await rpc<string[]>("llm.get_models", { base_url: url });
    if (res.ok && res.data) {
      setModels(res.data);
      if (res.data.length === 0) setStatus({ type: "error", msg: "No models found. Pull a model in Ollama first." });
    } else {
      setModels([]);
      setStatus({ type: "error", msg: res.error || "Could not connect to Ollama." });
    }
    setFetchingModels(false);
  }

  async function handleSaveLLM() {
    setSaving(true);
    setStatus(null);
    const res = await rpc<LLMConfig>("llm.save_config", { config });
    setStatus(res.ok ? { type: "success", msg: "Settings saved." } : { type: "error", msg: res.error || "Failed to save settings." });
    setSaving(false);
  }

  // -- Profile -------------------------------------------------------------

  async function loadSupportedCountries() {
    const res = await rpc<string[]>("tax.supported_countries");
    if (res.ok && res.data) setSupportedCountries(res.data);
  }

  async function loadProfile() {
    setProfileLoading(true);
    const res = await rpc<Entity>("users.get_active");
    if (res.ok && res.data) {
      const d = res.data as Entity;
      setIsDemoUser(!!d.is_demo);
      const p = d.profile as Entity | undefined;
      if (p) {
        const addr = p.address as Entity | undefined;
        setProfile({
          name: str(p, "name"),
          subtitle: str(p, "subtitle"),
          email: str(p, "email"),
          phone_number: str(p, "phone_number"),
          website: str(p, "website"),
          VAT_number: str(p, "VAT_number"),
          operating_country: str(p, "operating_country") || "Germany",
          street: addr ? str(addr, "street") : "",
          number: addr ? str(addr, "number") : "",
          postal_code: addr ? str(addr, "postal_code") : "",
          city: addr ? str(addr, "city") : "",
          country: addr ? str(addr, "country") : "",
        });
      }
    }
    setProfileLoading(false);
  }

  async function handleSaveProfile() {
    setProfileSaving(true);
    setProfileStatus(null);
    const payload = {
      profile: {
        name: profile.name,
        subtitle: profile.subtitle,
        email: profile.email,
        phone_number: profile.phone_number,
        website: profile.website,
        VAT_number: profile.VAT_number,
        operating_country: profile.operating_country,
        address: {
          street: profile.street,
          number: profile.number,
          postal_code: profile.postal_code,
          city: profile.city,
          country: profile.country,
        },
      },
    };
    const res = await rpc("users.update_profile", payload);
    setProfileStatus(res.ok ? { type: "success", msg: "Profile saved." } : { type: "error", msg: res.error || "Failed to save profile." });
    setProfileSaving(false);
  }

  async function handleResetDemo() {
    if (!confirm("This will delete all demo data and recreate it from scratch. Continue?")) return;
    setResettingDemo(true);
    setProfileStatus(null);
    const res = await rpc("demo.reset");
    if (res.ok) {
      setProfileStatus({ type: "success", msg: "Demo data has been reset." });
      await loadProfile();
    } else {
      setProfileStatus({ type: "error", msg: res.error || "Failed to reset demo data." });
    }
    setResettingDemo(false);
  }

  function pset<K extends keyof ProfileForm>(key: K) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setProfile((p) => ({ ...p, [key]: e.target.value }));
  }

  // -- Invoicing preferences -----------------------------------------------

  async function loadInvoicingPrefs() {
    const [prefsRes, tmplRes, langRes, schemeRes] = await Promise.all([
      rpc<InvoicingPrefs>("preferences.get"),
      rpc<Record<string, string>>("invoicing.available_templates"),
      rpc<Record<string, string>>("invoicing.available_languages"),
      rpc<Record<string, string>>("invoicing.available_number_schemes"),
    ]);
    if (prefsRes.ok && prefsRes.data) setInvoicing(prefsRes.data);
    if (tmplRes.ok && tmplRes.data) setAvailableTemplates(tmplRes.data);
    if (langRes.ok && langRes.data) setAvailableLanguages(langRes.data);
    if (schemeRes.ok && schemeRes.data) setAvailableSchemes(schemeRes.data);
  }

  async function handleSaveInvoicing() {
    setInvoicingSaving(true);
    setInvoicingStatus(null);
    const res = await rpc("preferences.save", {
      invoice_template: invoicing.invoice_template,
      language: invoicing.language,
      invoice_number_scheme: invoicing.invoice_number_scheme,
    });
    setInvoicingStatus(res.ok ? { type: "success", msg: "Invoicing preferences saved." } : { type: "error", msg: res.error || "Failed to save." });
    setInvoicingSaving(false);
  }

  // -- Render --------------------------------------------------------------

  if (loading || profileLoading) {
    return <div className="flex items-center justify-center h-full text-secondary">Loading settings…</div>;
  }

  const inputCls = "w-full px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors placeholder:text-muted";
  const labelCls = "block text-xs text-tertiary mb-1";

  return (
    <div className="flex h-full">
      {/* Sidebar tabs */}
      <nav className="w-48 shrink-0 border-r border-border-subtle py-4 px-2 space-y-1">
        <div className="flex items-center gap-2 px-3 pb-3">
          <Settings size={18} strokeWidth={1.6} className="text-secondary" />
          <span className="text-sm font-semibold">Settings</span>
        </div>
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm transition-colors ${
              tab === id
                ? "bg-accent/10 text-primary font-medium"
                : "text-secondary hover:bg-bg-hover hover:text-primary"
            }`}
          >
            <Icon size={15} />
            {label}
          </button>
        ))}
      </nav>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-xl">

      {tab === "profile" && (
        <section className="space-y-4">
          {isDemoUser && (
            <div className="flex items-center gap-3">
              <span className="inline-block text-[10px] text-muted bg-bg-hover px-2 py-0.5 rounded-full">
                demo user
              </span>
              <button
                onClick={handleResetDemo}
                disabled={resettingDemo}
                className="flex items-center gap-1.5 px-3 py-1 rounded-md text-xs text-secondary hover:text-primary border border-border-subtle hover:bg-bg-hover transition-colors disabled:opacity-40"
              >
                <RotateCcw size={12} className={resettingDemo ? "animate-spin" : ""} />
                {resettingDemo ? "Resetting…" : "Reset demo data"}
              </button>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className={labelCls}>Full name</label>
              <input className={inputCls} value={profile.name} onChange={pset("name")} />
            </div>
            <div className="col-span-2">
              <label className={labelCls}>Subtitle / profession</label>
              <input className={inputCls} value={profile.subtitle} onChange={pset("subtitle")} placeholder="Freelance consultant" />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Email</label>
              <input className={inputCls} type="email" value={profile.email} onChange={pset("email")} />
            </div>
            <div>
              <label className={labelCls}>Phone</label>
              <input className={inputCls} value={profile.phone_number} onChange={pset("phone_number")} />
            </div>
          </div>

          <div>
            <label className={labelCls}>Website</label>
            <input className={inputCls} value={profile.website} onChange={pset("website")} placeholder="https://…" />
          </div>

          <fieldset className="border border-border-subtle rounded-lg px-4 pb-3 pt-2">
            <legend className="text-xs font-medium text-secondary px-1">Address</legend>
            <div className="grid grid-cols-4 gap-3 mt-1">
              <div className="col-span-3">
                <label className={labelCls}>Street</label>
                <input className={inputCls} value={profile.street} onChange={pset("street")} />
              </div>
              <div>
                <label className={labelCls}>Nr.</label>
                <input className={inputCls} value={profile.number} onChange={pset("number")} />
              </div>
              <div>
                <label className={labelCls}>Postal code</label>
                <input className={inputCls} value={profile.postal_code} onChange={pset("postal_code")} />
              </div>
              <div className="col-span-2">
                <label className={labelCls}>City</label>
                <input className={inputCls} value={profile.city} onChange={pset("city")} />
              </div>
              <div>
                <label className={labelCls}>Country</label>
                <input className={inputCls} value={profile.country} onChange={pset("country")} />
              </div>
            </div>
          </fieldset>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>VAT number</label>
              <input className={inputCls} value={profile.VAT_number} onChange={pset("VAT_number")} placeholder="DE123456789" />
            </div>
            <div>
              <label className={labelCls}>Operating country</label>
              <select className={inputCls} value={profile.operating_country} onChange={pset("operating_country")}>
                {supportedCountries.length > 0 ? (
                  supportedCountries.map((c) => <option key={c} value={c}>{c}</option>)
                ) : (
                  <option value={profile.operating_country}>{profile.operating_country}</option>
                )}
              </select>
              <p className="mt-1 text-xs text-muted">Determines tax rules and default currency.</p>
            </div>
          </div>

          {profileStatus && (
            <div className={`flex items-center gap-2 text-sm ${profileStatus.type === "success" ? "text-green-400" : "text-red-400"}`}>
              {profileStatus.type === "success" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
              <span>{profileStatus.msg}</span>
            </div>
          )}

          <button
            onClick={handleSaveProfile}
            disabled={profileSaving || !profile.name.trim()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-accent/10 text-primary hover:bg-accent/20 border border-accent/30 transition-colors disabled:opacity-40"
          >
            <Save size={14} />
            {profileSaving ? "Saving…" : "Save Profile"}
          </button>
        </section>
      )}

      {tab === "invoicing" && (
        <section className="space-y-4">
          <div>
            <label className={labelCls}>Invoice template</label>
            <select
              className={inputCls}
              value={invoicing.invoice_template}
              onChange={(e) => setInvoicing((p) => ({ ...p, invoice_template: e.target.value }))}
            >
              {Object.entries(availableTemplates).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted">Visual style of generated invoices.</p>
          </div>

          <div>
            <label className={labelCls}>Invoice language</label>
            <select
              className={inputCls}
              value={invoicing.language}
              onChange={(e) => setInvoicing((p) => ({ ...p, language: e.target.value }))}
            >
              {Object.entries(availableLanguages).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted">Language for invoice labels, dates, and currency formatting.</p>
          </div>

          <div>
            <label className={labelCls}>Invoice number scheme</label>
            <select
              className={inputCls}
              value={invoicing.invoice_number_scheme}
              onChange={(e) => setInvoicing((p) => ({ ...p, invoice_number_scheme: e.target.value }))}
            >
              {Object.entries(availableSchemes).map(([key, label]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
            <p className="mt-1 text-xs text-muted">
              Example: <span className="font-mono text-primary">{SCHEME_EXAMPLES[invoicing.invoice_number_scheme] || "—"}</span>
            </p>
          </div>

          {invoicingStatus && (
            <div className={`flex items-center gap-2 text-sm ${invoicingStatus.type === "success" ? "text-green-400" : "text-red-400"}`}>
              {invoicingStatus.type === "success" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
              <span>{invoicingStatus.msg}</span>
            </div>
          )}

          <button
            onClick={handleSaveInvoicing}
            disabled={invoicingSaving}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-accent/10 text-primary hover:bg-accent/20 border border-accent/30 transition-colors disabled:opacity-40"
          >
            <Save size={14} />
            {invoicingSaving ? "Saving…" : "Save Invoicing Preferences"}
          </button>
        </section>
      )}

      {tab === "llm" && (
        <section className="space-y-4">
          <div>
            <label className={labelCls}>Provider</label>
            <select
              value={config.provider}
              onChange={(e) => setConfig((c) => ({ ...c, provider: e.target.value }))}
              className={inputCls}
            >
              <option value="ollama">Ollama</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>

          {config.provider === "ollama" && (
            <div>
              <label className={labelCls}>Ollama URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={config.base_url}
                  onChange={(e) => setConfig((c) => ({ ...c, base_url: e.target.value }))}
                  placeholder="http://localhost:11434"
                  className={`flex-1 ${inputCls}`}
                />
                <button
                  onClick={() => fetchModels()}
                  disabled={fetchingModels || !config.base_url}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium bg-bg-card text-secondary hover:text-primary border border-border-subtle transition-colors disabled:opacity-40"
                >
                  <RefreshCw size={14} className={fetchingModels ? "animate-spin" : ""} />
                  {fetchingModels ? "Fetching…" : "Fetch Models"}
                </button>
              </div>
            </div>
          )}

          {config.provider === "anthropic" && (
            <div>
              <label className={labelCls}>API Key</label>
              <input
                type="password"
                value={config.api_key}
                onChange={(e) => setConfig((c) => ({ ...c, api_key: e.target.value }))}
                placeholder="sk-ant-…"
                className={inputCls}
              />
            </div>
          )}

          <div>
            <label className={labelCls}>Model</label>
            {config.provider === "ollama" ? (
              models.length > 0 ? (
                <select value={config.model} onChange={(e) => setConfig((c) => ({ ...c, model: e.target.value }))} className={inputCls}>
                  <option value="">Select a model…</option>
                  {models.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              ) : (
                <div className="px-3 py-2 rounded-md text-sm bg-bg-card text-muted border border-border-subtle">
                  {fetchingModels ? "Fetching models…" : "No models available. Click \"Fetch Models\" to connect."}
                </div>
              )
            ) : (
              <input
                type="text"
                value={config.model}
                onChange={(e) => setConfig((c) => ({ ...c, model: e.target.value }))}
                placeholder="claude-sonnet-4-20250514"
                className={inputCls}
              />
            )}
          </div>

          <div>
            <label className={labelCls}>Request Timeout (seconds)</label>
            <input
              type="number"
              min={30}
              step={30}
              value={config.request_timeout}
              onChange={(e) => setConfig((c) => ({ ...c, request_timeout: Math.max(30, Number(e.target.value)) }))}
              className="w-32 px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors"
            />
            <p className="mt-1 text-xs text-muted">How long to wait for LLM responses. Increase for large documents or slow models.</p>
          </div>

          {status && (
            <div className={`flex items-center gap-2 text-sm ${status.type === "success" ? "text-green-400" : "text-red-400"}`}>
              {status.type === "success" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
              <span>{status.msg}</span>
            </div>
          )}

          <button
            onClick={handleSaveLLM}
            disabled={saving || !config.model}
            className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-accent/10 text-primary hover:bg-accent/20 border border-accent/30 transition-colors disabled:opacity-40"
          >
            <Save size={14} />
            {saving ? "Saving…" : "Save LLM Settings"}
          </button>
        </section>
      )}

        </div>
      </div>
    </div>
  );
}
