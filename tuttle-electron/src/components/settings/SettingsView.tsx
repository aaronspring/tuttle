import { useEffect, useState } from "react";
import { Settings, RefreshCw, Save, CheckCircle2, AlertCircle } from "lucide-react";
import { rpc } from "../../api/rpc";

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

export function SettingsView() {
  const [config, setConfig] = useState<LLMConfig>(DEFAULT_CONFIG);
  const [models, setModels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchingModels, setFetchingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  useEffect(() => { loadConfig(); }, []);

  async function loadConfig() {
    setLoading(true);
    const res = await rpc<LLMConfig>("llm.get_config");
    if (res.ok && res.data) {
      setConfig(res.data);
      if (res.data.base_url) {
        await fetchModels(res.data.base_url);
      }
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
      if (res.data.length === 0) {
        setStatus({ type: "error", msg: "No models found. Pull a model in Ollama first." });
      }
    } else {
      setModels([]);
      setStatus({ type: "error", msg: res.error || "Could not connect to Ollama." });
    }
    setFetchingModels(false);
  }

  async function handleSave() {
    setSaving(true);
    setStatus(null);
    const res = await rpc<LLMConfig>("llm.save_config", { config });
    if (res.ok) {
      setStatus({ type: "success", msg: "Settings saved." });
    } else {
      setStatus({ type: "error", msg: res.error || "Failed to save settings." });
    }
    setSaving(false);
  }

  if (loading) {
    return <div className="flex items-center justify-center h-full text-secondary">Loading settings…</div>;
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <div className="flex items-center gap-3">
        <Settings size={22} strokeWidth={1.6} className="text-secondary" />
        <h1 className="text-lg font-semibold">Settings</h1>
      </div>

      {/* LLM Configuration */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-secondary">AI / LLM Configuration</h2>

        {/* Provider */}
        <div>
          <label className="block text-xs text-tertiary mb-1">Provider</label>
          <select
            value={config.provider}
            onChange={(e) => setConfig((c) => ({ ...c, provider: e.target.value }))}
            className="w-full px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors"
          >
            <option value="ollama">Ollama</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>

        {config.provider === "ollama" && (
          <div>
            <label className="block text-xs text-tertiary mb-1">Ollama URL</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={config.base_url}
                onChange={(e) => setConfig((c) => ({ ...c, base_url: e.target.value }))}
                placeholder="http://localhost:11434"
                className="flex-1 px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors placeholder:text-muted"
              />
              <button
                onClick={() => fetchModels()}
                disabled={fetchingModels || !config.base_url}
                className="flex items-center gap-1.5 px-3 py-2 rounded-md text-sm font-medium bg-bg-card text-secondary hover:text-primary border border-border-subtle transition-colors disabled:opacity-40"
                title="Fetch available models"
              >
                <RefreshCw size={14} className={fetchingModels ? "animate-spin" : ""} />
                {fetchingModels ? "Fetching…" : "Fetch Models"}
              </button>
            </div>
          </div>
        )}

        {config.provider === "anthropic" && (
          <div>
            <label className="block text-xs text-tertiary mb-1">API Key</label>
            <input
              type="password"
              value={config.api_key}
              onChange={(e) => setConfig((c) => ({ ...c, api_key: e.target.value }))}
              placeholder="sk-ant-…"
              className="w-full px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors placeholder:text-muted"
            />
          </div>
        )}

        {/* Model Selection */}
        <div>
          <label className="block text-xs text-tertiary mb-1">Model</label>
          {config.provider === "ollama" ? (
            models.length > 0 ? (
              <select
                value={config.model}
                onChange={(e) => setConfig((c) => ({ ...c, model: e.target.value }))}
                className="w-full px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors"
              >
                <option value="">Select a model…</option>
                {models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
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
              className="w-full px-3 py-2 rounded-md text-sm bg-bg-card text-primary border border-border-subtle outline-none focus:border-accent transition-colors placeholder:text-muted"
            />
          )}
        </div>

        {/* Request Timeout */}
        <div>
          <label className="block text-xs text-tertiary mb-1">Request Timeout (seconds)</label>
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

        {/* Status */}
        {status && (
          <div className={`flex items-center gap-2 text-sm ${status.type === "success" ? "text-green-400" : "text-red-400"}`}>
            {status.type === "success" ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            <span>{status.msg}</span>
          </div>
        )}

        {/* Save */}
        <button
          onClick={handleSave}
          disabled={saving || !config.model}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md text-sm font-medium bg-accent/10 text-accent hover:bg-accent/20 border border-accent/30 transition-colors disabled:opacity-40"
        >
          <Save size={14} />
          {saving ? "Saving…" : "Save Settings"}
        </button>
      </section>
    </div>
  );
}
