import {
  createContext,
  useContext,
  useCallback,
  useState,
  useRef,
  type ReactNode,
} from "react";

export type MessageType = "info" | "error" | "success";

export interface StatusMessage {
  id: number;
  text: string;
  type: MessageType;
  timestamp: Date;
}

interface ShowMessageOpts {
  type?: MessageType;
  /** Auto-dismiss duration in ms. Defaults to 5000; errors default to 8000. */
  duration?: number;
}

interface StatusBarContextValue {
  active: StatusMessage | null;
  log: StatusMessage[];
  showMessage: (text: string, opts?: ShowMessageOpts) => void;
  dismiss: () => void;
}

const StatusBarContext = createContext<StatusBarContextValue>({
  active: null,
  log: [],
  showMessage: () => {},
  dismiss: () => {},
});

const MAX_LOG_SIZE = 50;

export function StatusBarProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<StatusMessage | null>(null);
  const [log, setLog] = useState<StatusMessage[]>([]);
  const nextId = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const dismiss = useCallback(() => setActive(null), []);

  const showMessage = useCallback(
    (text: string, opts: ShowMessageOpts = {}) => {
      const type = opts.type ?? "info";
      const duration =
        opts.duration ?? (type === "error" ? 8000 : 5000);

      const msg: StatusMessage = {
        id: nextId.current++,
        text,
        type,
        timestamp: new Date(),
      };

      setActive(msg);
      setLog((prev) => [msg, ...prev].slice(0, MAX_LOG_SIZE));

      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setActive(null), duration);
    },
    [],
  );

  return (
    <StatusBarContext.Provider value={{ active, log, showMessage, dismiss }}>
      {children}
    </StatusBarContext.Provider>
  );
}

export function useStatusBar() {
  return useContext(StatusBarContext);
}
