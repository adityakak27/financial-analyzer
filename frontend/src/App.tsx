import { BrowserRouter, Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import { SelectionProvider } from "./context/SelectionContext";
import ChatPage from "./pages/ChatPage";
import ComparePage from "./pages/ComparePage";
import DashboardPage from "./pages/DashboardPage";
import FilingsPage from "./pages/FilingsPage";
import ResearchPage from "./pages/ResearchPage";
import ValuationPage from "./pages/ValuationPage";

export default function App() {
  return (
    <SelectionProvider>
      <BrowserRouter>
        <div className="app-shell">
          <Sidebar />
          <main className="main">
            <Routes>
              <Route path="/" element={<ChatPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/valuation" element={<ValuationPage />} />
              <Route path="/research" element={<ResearchPage />} />
              <Route path="/filings" element={<FilingsPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </SelectionProvider>
  );
}
