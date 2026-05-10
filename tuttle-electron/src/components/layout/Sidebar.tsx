import {
  LayoutDashboard, CalendarDays, PieChart, Banknote,
  FolderKanban, FileSignature, Building2, Users, Clock, FileText,
  type LucideIcon,
} from "lucide-react";

type SidebarItem = { id: string; label: string; icon: LucideIcon };

const SECTIONS: { label: string; items: SidebarItem[] }[] = [
  {
    label: "Insights",
    items: [
      { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { id: "timeline", label: "Timeline", icon: CalendarDays },
      { id: "tax", label: "Tax & Reserves", icon: PieChart },
      { id: "salary", label: "Salary", icon: Banknote },
    ],
  },
  {
    label: "My Business",
    items: [
      { id: "projects", label: "Projects", icon: FolderKanban },
      { id: "contracts", label: "Contracts", icon: FileSignature },
      { id: "clients", label: "Clients", icon: Building2 },
      { id: "contacts", label: "Contacts", icon: Users },
    ],
  },
  {
    label: "Workflows",
    items: [
      { id: "timetracking", label: "Time Tracking", icon: Clock },
      { id: "invoicing", label: "Invoicing", icon: FileText },
    ],
  },
];

type Props = {
  selected: string;
  onSelect: (id: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
};

export function Sidebar({ selected, onSelect, collapsed }: Props) {
  return (
    <aside className={`flex flex-col bg-bg-sidebar border-r border-border-subtle transition-all duration-200 ${collapsed ? "w-14" : "w-52"}`}>
      <div className="drag-region h-13 flex items-end px-4 pb-2 shrink-0">
        {!collapsed && <span className="text-sm font-semibold tracking-wide">Tuttle</span>}
      </div>

      <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-4">
        {SECTIONS.map((section) => (
          <div key={section.label}>
            {!collapsed && (
              <div className="px-2 pb-1 text-xs font-semibold uppercase tracking-widest text-accent">
                {section.label}
              </div>
            )}
            <div className="space-y-0.5">
              {section.items.map((item) => {
                const active = selected === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelect(item.id)}
                    className={`no-drag flex items-center gap-2.5 w-full rounded-md px-2.5 py-1.5 text-sm transition-colors cursor-default
                      ${active ? "bg-bg-selected text-primary" : "text-secondary hover:bg-bg-hover hover:text-primary"}
                      ${collapsed ? "justify-center" : ""}`}
                    title={collapsed ? item.label : undefined}
                  >
                    <item.icon size={16} strokeWidth={1.8} className="shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
