import { LogOut, MessageCircle, Search, Settings } from "lucide-react";

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Primary navigation">
      <div className="brand">C</div>
      <nav className="rail-nav">
        <button className="rail-button active" aria-label="Copilot">
          <Search size={16} />
        </button>
        <button className="rail-button" aria-label="Messages">
          <MessageCircle size={16} />
        </button>
        <button className="rail-button" aria-label="Settings">
          <Settings size={16} />
        </button>
      </nav>
      <button className="rail-button rail-exit" aria-label="Sign out">
        <LogOut size={16} />
      </button>
    </aside>
  );
}
