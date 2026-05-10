import { List, LayoutGrid } from "lucide-react";

type Props = { mode: "list" | "board"; onChange: (m: "list" | "board") => void };

export function ViewModeToggle({ mode, onChange }: Props) {
  return (
    <div className="inline-flex rounded-md overflow-hidden border border-border">
      {(["list", "board"] as const).map((m) => (
        <button key={m} onClick={() => onChange(m)} title={`${m} view`}
          className={`flex items-center justify-center w-8 h-7 transition-colors
            ${m === mode ? "bg-bg-selected text-primary" : "text-tertiary hover:text-secondary"}
            ${m === "board" ? "border-l border-border" : ""}`}>
          {m === "list" ? <List size={14} /> : <LayoutGrid size={14} />}
        </button>
      ))}
    </div>
  );
}
