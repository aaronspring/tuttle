import { useState, useCallback, useMemo, useEffect } from "react";
import { Sidebar, type RegisteredUser } from "./Sidebar";
import { UserRegistrationDialog, type UserFormData } from "./UserRegistrationDialog";
import { DashboardView } from "../dashboard/DashboardView";
import { ProjectsView } from "../business/ProjectsView";
import { ClientsView } from "../business/ClientsView";
import { ContractsView } from "../business/ContractsView";
import { InvoicingView } from "../invoicing/InvoicingView";
import { ContactsView } from "../contacts/ContactsView";
import { SettingsView } from "../settings/SettingsView";
import { TimelineView } from "../timeline/TimelineView";
import { TaxReservesView } from "../tax/TaxReservesView";
import { SalaryView } from "../salary/SalaryView";
import { TimeTrackingView } from "../timetracking/TimeTrackingView";
import { ContractImportView } from "../import/ContractImportView";
import { PlaceholderView } from "../shared/PlaceholderView";
import { NavigationContext, type NavigationFilter } from "../shared/NavigationContext";
import { rpc } from "../../api/rpc";

type BootState = "loading" | "welcome" | "ready";

export function Shell() {
  const [bootState, setBootState] = useState<BootState>("loading");
  const [selected, setSelected] = useState("dashboard");
  const [collapsed, setCollapsed] = useState(false);
  const [navFilter, setNavFilter] = useState<NavigationFilter>({});
  const [activeUser, setActiveUser] = useState<RegisteredUser | null>(null);
  const [allUsers, setAllUsers] = useState<RegisteredUser[]>([]);
  const [regDialogOpen, setRegDialogOpen] = useState(false);
  const [regLoading, setRegLoading] = useState(false);

  const navigate = useCallback((view: string, filter?: NavigationFilter) => {
    setNavFilter(filter || {});
    setSelected(view);
  }, []);

  const navContext = useMemo(
    () => ({ navigate, filter: navFilter }),
    [navigate, navFilter],
  );

  async function refreshUsers() {
    const res = await rpc<RegisteredUser[]>("users.list");
    if (res.ok && res.data) setAllUsers(res.data);
  }

  async function refreshActiveUser() {
    const res = await rpc<RegisteredUser | null>("users.get_active");
    if (res.ok && res.data) setActiveUser(res.data);
    else setActiveUser(null);
  }

  useEffect(() => {
    (async () => {
      await rpc("db.ensure");
      const usersRes = await rpc<RegisteredUser[]>("users.list");
      const users = usersRes.ok && usersRes.data ? usersRes.data : [];
      setAllUsers(users);

      if (users.length === 0) {
        setBootState("welcome");
      } else {
        await refreshActiveUser();
        setBootState("ready");
      }
    })();
  }, []);

  async function handleWelcomeDemo() {
    setBootState("loading");
    await rpc("users.ensure_demo");
    await refreshUsers();
    const demoSwitch = await rpc("users.switch", { db_file: "harry-tuttle.db" });
    if (demoSwitch.ok) {
      await refreshActiveUser();
    }
    setBootState("ready");
  }

  async function handleWelcomeCreate() {
    setBootState("loading");
    setRegDialogOpen(true);
  }

  async function handleSwitchUser(dbFile: string) {
    await rpc("users.switch", { db_file: dbFile });
    await refreshActiveUser();
    setSelected("dashboard");
    window.location.reload();
  }

  async function handleDeleteUser(dbFile: string) {
    await rpc("users.delete", { db_file: dbFile });
    await refreshUsers();
    const remaining = allUsers.filter((u) => u.db_file !== dbFile);
    if (activeUser?.db_file === dbFile && remaining.length > 0) {
      await handleSwitchUser(remaining[0].db_file);
    } else if (remaining.length === 0) {
      setActiveUser(null);
      setBootState("welcome");
    }
  }

  async function handleRegSubmit(data: UserFormData) {
    setRegLoading(true);
    const res = await rpc<RegisteredUser>("users.create", data as unknown as Record<string, unknown>);
    setRegLoading(false);
    setRegDialogOpen(false);
    if (res.ok && res.data) {
      if (data.invoice_number_scheme) {
        await rpc("preferences.save", { invoice_number_scheme: data.invoice_number_scheme });
      }
      await refreshUsers();
      await refreshActiveUser();
      setBootState("ready");
      window.location.reload();
    }
  }

  function handleSidebarSelect(id: string) {
    setNavFilter({});
    setSelected(id);
  }

  if (bootState === "loading") {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-bg-content text-secondary">
        <div className="text-center space-y-2">
          <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm">Loading Tuttle…</p>
        </div>
      </div>
    );
  }

  if (bootState === "welcome") {
    return (
      <>
        <div className="flex h-screen w-screen items-center justify-center bg-bg-content">
          <div className="text-center space-y-6 max-w-md mx-4">
            <h1 className="text-2xl font-bold text-primary">Welcome to Tuttle</h1>
            <p className="text-secondary text-sm leading-relaxed">
              Tuttle helps freelancers manage clients, contracts, invoicing and time tracking.
              Get started by creating your profile or exploring with demo data.
            </p>
            <div className="flex flex-col gap-3 items-center">
              <button
                onClick={handleWelcomeCreate}
                className="w-64 px-5 py-2.5 rounded-lg bg-accent text-white font-medium text-sm hover:bg-accent/90 transition-colors"
              >
                Create my profile
              </button>
              <button
                onClick={handleWelcomeDemo}
                className="w-64 px-5 py-2.5 rounded-lg border border-border-subtle text-secondary text-sm hover:bg-bg-hover hover:text-primary transition-colors"
              >
                Try with demo data
              </button>
            </div>
          </div>
        </div>
        <UserRegistrationDialog
          open={regDialogOpen}
          onClose={() => { setRegDialogOpen(false); setBootState("welcome"); }}
          onSubmit={handleRegSubmit}
          loading={regLoading}
        />
      </>
    );
  }

  return (
    <NavigationContext.Provider value={navContext}>
      <div className="flex h-screen w-screen bg-bg-content text-primary">
        <Sidebar
          selected={selected}
          onSelect={handleSidebarSelect}
          collapsed={collapsed}
          onToggleCollapse={() => setCollapsed((c) => !c)}
          activeUser={activeUser}
          allUsers={allUsers}
          onSwitchUser={handleSwitchUser}
          onAddUser={() => setRegDialogOpen(true)}
          onDeleteUser={handleDeleteUser}
        />
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="drag-region h-13 shrink-0" />
          <div className="flex-1 overflow-y-auto">
            <DetailView id={selected} />
          </div>
        </main>
      </div>
      <UserRegistrationDialog
        open={regDialogOpen}
        onClose={() => setRegDialogOpen(false)}
        onSubmit={handleRegSubmit}
        loading={regLoading}
      />
    </NavigationContext.Provider>
  );
}

function DetailView({ id }: { id: string }) {
  switch (id) {
    case "dashboard": return <DashboardView />;
    case "timeline": return <TimelineView />;
    case "tax": return <TaxReservesView />;
    case "salary": return <SalaryView />;
    case "clients": return <ClientsView />;
    case "contracts": return <ContractsView />;
    case "projects": return <ProjectsView />;
    case "contacts": return <ContactsView />;
    case "timetracking": return <TimeTrackingView />;
    case "invoicing": return <InvoicingView />;
    case "import": return <ContractImportView />;
    case "settings": return <SettingsView />;
    default: return <PlaceholderView title={id.charAt(0).toUpperCase() + id.slice(1)} />;
  }
}
