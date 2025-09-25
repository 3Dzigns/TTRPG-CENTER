import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { useThemeStore } from './stores/themeStore';
import Layout from './components/Layout';
import ChatPage from './pages/ChatPage';
import PlanPage from './pages/PlanPage';
import HistoryPage from './pages/HistoryPage';
import SettingsPage from './pages/SettingsPage';

function App() {
  const { theme } = useThemeStore();

  return (
    <div className={`${theme === 'terminal' ? 'terminal-container' : 'lcars-container'} scan-lines`}>
      <Layout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </div>
  );
}

export default App;