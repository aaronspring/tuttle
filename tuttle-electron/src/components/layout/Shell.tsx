import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { DashboardView } from "../dashboard/DashboardView";
import { ProjectsView } from "../business/ProjectsView";
import { InvoicingView } from "../invoicing/InvoicingView";
import { ContactsView } from "../contacts/ContactsView";
import { PlaceholderView } from "../shared/PlaceholderView";
import { rpc } from "../../api/rpc";
import { Database } from "lucide-react";

export function Shell() {
  const [selected, setSelected] = useState("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [installingDemo, setInstallingDemo] = useState(false);

  async function installDemo() {
    setInstallingDemo(true);
    await rpc("demo.install", { n_projects: 4 });
    setInstallingDemo(false);
    setSelected("dashboard");
    window.location.reload();
  }

  return (
    <div className="flex h-screen w-screen bg-bg-content text-primary">
      <Sidebar selected={selected} onSelect={setSelected}
        collapsed={collapsed} onToggleCollapse={() => setCollapsed((c) => !c)} />
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="drag-region h-13 shrink-0 flex items-end justify-end px-4 pb-2">
          <button onClick={installDemo} disabled={installingDemo}
            className="no-drag flex items-center gap-1.5 text-xs text-muted hover:text-secondary transition-colors disabled:opacity-40"
            title="Install demo data">
            <Database size={13} />
            {installingDemo ? "Installing…" : "Demo Data"}
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          <DetailView id={selected} />
        </div>
      </main>
    </div>
  );
}

function DetailView({ id }: { id: string }) {
  switch (id) {
    case "dashboard": return <DashboardView />;
    case "projects": return <ProjectsView />;
    case "contacts": return <ContactsView />;
    case "invoicing": return <InvoicingView />;
    default: return <PlaceholderView title={id.charAt(0).toUpperCase() + id.slice(1)} />;
  }
}
