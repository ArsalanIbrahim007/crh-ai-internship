import { CopilotPage } from "./pages/CopilotPage";
import { Sidebar } from "./components/layout/Sidebar";

export function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <CopilotPage />
    </div>
  );
}
