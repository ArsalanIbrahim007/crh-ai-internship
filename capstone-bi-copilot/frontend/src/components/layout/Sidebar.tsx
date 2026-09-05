import { BarChart3, CalendarDays, FileText, Link2, MessageSquare, Sparkles } from "lucide-react";
import type { ReactNode, RefObject } from "react";
import type { AppView } from "../../App";

interface SidebarProps {
  activeView: AppView;
  hasActiveConversation: boolean;
  orbTargetRef: RefObject<HTMLDivElement | null>;
  onNewChat: () => void;
  onNavigate: (view: AppView) => void;
}

export function Sidebar({ activeView, hasActiveConversation, orbTargetRef, onNewChat, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="sidebar-top">
        <div ref={orbTargetRef} className="sidebar-orb-slot" aria-hidden="true" />
      </div>
      <nav className="rail-nav" aria-label="Copilot navigation">
        <RailButton active={activeView === "copilot" && !hasActiveConversation} label="New Chat" ariaLabel="Start new chat" onClick={onNewChat}>
          <Sparkles />
        </RailButton>
        <RailButton active={activeView === "history"} label="Chat History" ariaLabel="Open chat history" onClick={() => onNavigate("history")}>
          <MessageSquare />
        </RailButton>
        <RailButton active={activeView === "documents"} label="Documents" ariaLabel="Open documents" onClick={() => onNavigate("documents")}>
          <FileText />
        </RailButton>
                <RailButton active={activeView === "calendar"} label="Calendar" ariaLabel="Open calendar" onClick={() => onNavigate("calendar")}><CalendarDays /></RailButton>
        <RailButton active={activeView === "analytics"} label="Analytics" ariaLabel="Open analytics" onClick={() => onNavigate("analytics")}><BarChart3 /></RailButton>
        <RailButton active={activeView === "connections"} label="Connections" ariaLabel="Open connections" onClick={() => onNavigate("connections")}><Link2 /></RailButton>
      </nav>
    </aside>
  );
}

interface RailButtonProps {
  active?: boolean;
  ariaLabel: string;
  children: ReactNode;
  label: string;
  onClick?: () => void;
}

function RailButton({ active, ariaLabel, children, label, onClick }: RailButtonProps) {
  return (
    <button type="button" className={`rail-button ${active ? "active" : ""}`.trim()} aria-label={ariaLabel} aria-current={active ? "page" : undefined} onClick={onClick}>
      {children}
      <span className="rail-tooltip" role="tooltip">{label}</span>
    </button>
  );
}
