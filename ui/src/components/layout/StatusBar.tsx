import { AlertCircle, CheckCircle2, Info, MessageCircleQuestion, Bug } from "lucide-react";
import { useStatusBar, type MessageType } from "../shared/status-bar-context";
import { useNavigation } from "../shared/NavigationContext";

const REPO = "https://github.com/tuttle-dev/tuttle";

const ICONS: Record<MessageType, typeof Info> = {
  info: Info,
  error: AlertCircle,
  success: CheckCircle2,
};

const TYPE_STYLES: Record<MessageType, string> = {
  info: "text-secondary",
  error: "text-red-400",
  success: "text-green-400",
};

const linkCls =
  "flex items-center gap-1 text-muted hover:text-secondary transition-colors";

export function StatusBar() {
  const { active, dismiss } = useStatusBar();
  const { navigate } = useNavigation();

  function handleClick() {
    if (active?.type === "error") {
      navigate("settings", {});
      dismiss();
    }
  }

  function open(url: string) {
    if (window.tuttle?.openExternal) {
      window.tuttle.openExternal(url);
    } else {
      window.open(url, "_blank");
    }
  }

  const idleContent = (
    <div className="flex items-center gap-3 ml-auto">
      <button onClick={() => open(`${REPO}/discussions`)} className={linkCls}>
        <MessageCircleQuestion size={13} />
        <span>Ask a question</span>
      </button>
      <button onClick={() => open(`${REPO}/issues/new`)} className={linkCls}>
        <Bug size={13} />
        <span>Report an issue</span>
      </button>
    </div>
  );

  if (active) {
    const Icon = ICONS[active.type];
    return (
      <div
        role={active.type === "error" ? "button" : undefined}
        tabIndex={active.type === "error" ? 0 : undefined}
        onClick={handleClick}
        onKeyDown={(e) => e.key === "Enter" && handleClick()}
        className={`shrink-0 flex items-center gap-2 px-4 h-7 border-t border-border-subtle bg-bg-sidebar text-xs select-none ${
          active.type === "error" ? "cursor-pointer hover:bg-bg-hover" : ""
        }`}
      >
        <Icon size={13} className={TYPE_STYLES[active.type]} />
        <span className={`truncate ${TYPE_STYLES[active.type]}`}>
          {active.text}
        </span>
      </div>
    );
  }

  return (
    <div className="shrink-0 flex items-center gap-2 px-4 h-7 border-t border-border-subtle bg-bg-sidebar text-xs select-none">
      {idleContent}
    </div>
  );
}
