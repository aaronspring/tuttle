import { useState, useEffect } from "react";
import { Download, X } from "lucide-react";
import { useStatusBar } from "../shared/status-bar-context";

export function UpdateBanner() {
  const [update, setUpdate] = useState<{ version: string } | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const { showMessage } = useStatusBar();

  useEffect(() => {
    window.tuttle?.onUpdateDownloaded?.((info) => setUpdate(info));
    window.tuttle?.onUpdateError?.((info) => {
      showMessage(`Update check failed: ${info.message}`, { type: "error" });
    });
  }, []);

  if (!update || dismissed) return null;

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-accent/10 border-b border-accent/20 text-sm text-primary shrink-0">
      <Download size={16} className="text-accent shrink-0" />
      <span className="flex-1">
        Tuttle <strong>{update.version}</strong> is ready to install.
      </span>
      <button
        onClick={() => window.tuttle.quitAndInstall()}
        className="px-3 py-1 rounded-md bg-accent text-white text-xs font-medium hover:bg-accent/90 transition-colors"
      >
        Restart &amp; Update
      </button>
      <button
        onClick={() => setDismissed(true)}
        className="p-1 rounded hover:bg-white/10 transition-colors text-secondary"
        aria-label="Dismiss"
      >
        <X size={14} />
      </button>
    </div>
  );
}
