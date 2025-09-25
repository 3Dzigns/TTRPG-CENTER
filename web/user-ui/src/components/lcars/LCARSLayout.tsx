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

interface LCARSLayoutProps {
  children: React.ReactNode;
  currentPath: string;
}

export default function LCARSLayout({ children, currentPath }: LCARSLayoutProps) {
  const { toggleTheme } = useThemeStore();
  const { getCurrentSession } = useSessionStore();

  const currentSession = getCurrentSession();
  const sessionName = currentSession?.name || 'No Active Session';

  const navigationItems = [
    { path: '/chat', icon: MessageCircle, label: 'COMMUNICATE', color: 'bg-lcars-orange' },
    { path: '/plan', icon: PlanPlay, label: 'TACTICAL', color: 'bg-lcars-blue' },
    { path: '/history', icon: History, label: 'RECORDS', color: 'bg-lcars-red' },
    { path: '/settings', icon: Settings, label: 'SYSTEMS', color: 'bg-lcars-purple' }
  ];

  return (
    <div className="lcars-container">
      {/* LCARS Header */}
      <div className="lcars-header">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3 text-black font-bold">
            <Terminal className="h-8 w-8" />
            <div className="text-2xl">TTRPG CENTER</div>
          </div>
          <div className="bg-black text-lcars-yellow px-4 py-1 rounded-lcars font-bold text-sm">
            SESSION: {sessionName.toUpperCase()}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="bg-black text-lcars-blue px-3 py-1 rounded-lcars text-sm font-mono">
            {new Date().toLocaleTimeString()}
          </div>
          <button
            onClick={toggleTheme}
            className="bg-lcars-yellow hover:bg-lcars-yellow/80 text-black px-4 py-2 rounded-lcars-pill font-bold transition-all duration-200 active:scale-95"
            title="Switch to Terminal interface"
          >
            <Zap className="h-4 w-4 inline mr-2" />
            TERMINAL
          </button>
        </div>
      </div>

      {/* LCARS Navigation Panel */}
      <div className="flex">
        <div className="w-64 bg-lcars-panel/20 border-r-4 border-lcars-orange">
          <div className="p-4 space-y-2">
            {navigationItems.map(({ path, icon: Icon, label, color }) => (
              <Link
                key={path}
                to={path}
                className={`
                  flex items-center gap-3 p-3 rounded-lcars font-lcars font-bold text-black
                  transition-all duration-200 active:scale-95
                  ${currentPath === path
                    ? `${color} animate-lcars-pulse`
                    : `${color}/70 hover:${color}`
                  }
                `}
              >
                <Icon className="h-5 w-5" />
                {label}
              </Link>
            ))}
          </div>

          {/* LCARS Status Panel */}
          <div className="p-4 mt-8">
            <div className="bg-lcars-orange p-3 rounded-lcars text-black font-bold mb-2">
              SYSTEM STATUS
            </div>
            <div className="space-y-1 text-lcars-yellow text-sm font-mono">
              <div className="flex justify-between">
                <span>CORE:</span>
                <span className="text-lcars-blue">ONLINE</span>
              </div>
              <div className="flex justify-between">
                <span>COMMS:</span>
                <span className="text-lcars-blue">ACTIVE</span>
              </div>
              <div className="flex justify-between">
                <span>SHIELDS:</span>
                <span className="text-lcars-red">100%</span>
              </div>
              <div className="flex justify-between">
                <span>POWER:</span>
                <span className="text-lcars-blue">NOMINAL</span>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col">
          {/* Content Status Bar */}
          <div className="flex items-center justify-between p-2 bg-lcars-panel/10 border-b-2 border-lcars-blue">
            <div className="flex items-center gap-4 text-lcars-yellow text-sm">
              <div className="bg-lcars-blue px-2 py-1 rounded text-black font-bold">ACTIVE</div>
              <span>Environment: {import.meta.env.MODE?.toUpperCase() || 'DEVELOPMENT'}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-lcars-blue rounded-full animate-pulse"></div>
              <span className="text-lcars-blue font-bold">OPERATIONAL</span>
            </div>
          </div>

          {/* Main Content */}
          <div className="flex-1 overflow-hidden bg-lcars-bg/50">
            {children}
          </div>
        </div>
      </div>

      {/* LCARS Footer */}
      <div className="flex items-center justify-between p-3 bg-gradient-to-r from-lcars-blue to-lcars-purple">
        <div className="text-xs text-black font-bold">
          TTRPG CENTER USER INTERFACE v2.0.0 | STARDATE: {Math.floor(Date.now() / 86400000) + 2400000}
        </div>
        <div className="flex items-center gap-2">
          <Power className="h-4 w-4 text-black" />
          <span className="text-black font-bold text-xs">MAIN POWER</span>
        </div>
      </div>
    </div>
  );
}