const STATUS_COLORS: Record<string, string> = {
  active: "#34d399", upcoming: "#60a5fa", completed: "#a0a0a0",
  draft: "#a0a0a0", sent: "#60a5fa", paid: "#34d399",
  overdue: "#f87171", cancelled: "#fb923c",
  lead: "#c084fc", offer: "#fb923c",
};

type Props = { status: string; className?: string };

export function StatusBadge({ status, className = "" }: Props) {
  const color = STATUS_COLORS[status.toLowerCase()] || "#a0a0a0";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ${className}`}
      style={{ background: `${color}1a`, color, border: `1px solid ${color}33` }}>
      {status}
    </span>
  );
}
