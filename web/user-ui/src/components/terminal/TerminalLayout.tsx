import React from 'react';
import { Link } from 'react-router-dom';
import { useThemeStore } from '../../stores/themeStore';
import { useSessionStore } from '../../stores/sessionStore';
import {
  Terminal,
  MessageCircle,
  PlanPlay,
  History,
  Settings,
  Power,
  Zap
} from 'lucide-react';

interface TerminalLayoutProps {
  children: React.ReactNode;
  currentPath: string;
}

export default function TerminalLayout({ children, currentPath }: TerminalLayoutProps) {
  const { toggleTheme } = useThemeStore();
  const { getCurrentSession } = useSessionStore();

  const currentSession = getCurrentSession();
  const sessionName = currentSession?.name || 'No Active Session';

  const navigationItems = [
    { path: '/chat', icon: MessageCircle, label: 'CHAT', description: 'Natural language queries' },
    { path: '/plan', icon: PlanPlay, label: 'PLAN', description: 'Workflow planning' },
    { path: '/history', icon: History, label: 'HIST', description: 'Session history' },
    { path: '/settings', icon: Settings, label: 'SETT', description: 'Configuration' }
  ];

  return (
    <div className="terminal-container terminal-screen">
      {/* Terminal Header */}
      <div className="terminal-header">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-terminal-text retro-glow">
            <Terminal className="h-6 w-6" />
            <span className="font-bold text-xl">TTRPG_CENTER_V2.0</span>
          </div>
          <div className="text-terminal-amber text-sm">
            SESSION: {sessionName.toUpperCase()}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="text-terminal-blue text-sm">
            {new Date().toLocaleTimeString()}
          </div>
          <button
            onClick={toggleTheme}
            className="flex items-center gap-1 text-terminal-amber hover:text-terminal-text transition-colors"
            title="Switch to LCARS interface"
          >
            <Zap className="h-4 w-4" />
            LCARS
          </button>
        </div>
      </div>

      {/* Navigation Bar */}
      <div className="flex border-b border-terminal-text/20 bg-black/30">
        {navigationItems.map(({ path, icon: Icon, label, description }) => (
          <Link
            key={path}
            to={path}
            className={`
              flex items-center gap-2 px-6 py-3 border-r border-terminal-text/20
              transition-all duration-200 group
              ${currentPath === path
                ? 'bg-terminal-text/10 text-terminal-text retro-glow'
                : 'text-terminal-text/70 hover:text-terminal-text hover:bg-terminal-text/5'
              }
            `}
            title={description}
          >
            <Icon className="h-4 w-4" />
            <span className="font-mono font-bold">[{label}]</span>
          </Link>
        ))}
      </div>

      {/* Status Line */}
      <div className="flex items-center justify-between px-4 py-1 bg-black/50 border-b border-terminal-text/10 text-xs">
        <div className="flex items-center gap-4 text-terminal-text/50">
          <span>SYSTEM: ONLINE</span>
          <span>CPU: 23%</span>
          <span>MEM: 1.2GB</span>
          <span>NET: CONNECTED</span>
        </div>
        <div className="flex items-center gap-2 text-terminal-amber">
          <div className="w-2 h-2 bg-terminal-text rounded-full animate-pulse"></div>
          <span>READY</span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {children}
      </div>

      {/* Terminal Footer */}
      <div className="terminal-header border-t border-terminal-text/20">
        <div className="text-xs text-terminal-text/50">
          TTRPG Center User Interface v2.0.0 | Environment: {import.meta.env.MODE?.toUpperCase() || 'DEV'}
        </div>
        <div className="flex items-center gap-2 text-xs text-terminal-red">
          <Power className="h-3 w-3" />
          <span>PWR</span>
        </div>
      </div>
    </div>
  );
}