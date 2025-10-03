/**
 * Settings Page Component
 *
 * Complete settings interface with theme switching, preferences, and configuration
 */

import React, { useState, useEffect } from 'react';
import { useThemeStore } from '../stores/themeStore';
import { useSessionStore } from '../stores/sessionStore';
import {
  Settings,
  Palette,
  Monitor,
  Terminal,
  User,
  Bell,
  Shield,
  Download,
  Trash2,
  RefreshCw,
  Save,
  Volume2,
  VolumeX,
  Eye,
  Accessibility,
  Keyboard,
  Globe,
  Database,
  Activity
} from 'lucide-react';

interface UserPreferences {
  responseLength: 'short' | 'medium' | 'long';
  autoSave: boolean;
  soundEnabled: boolean;
  animations: boolean;
  fontSize: 'small' | 'medium' | 'large';
  highContrast: boolean;
  reducedMotion: boolean;
  saveHistory: boolean;
  autoComplete: boolean;
  keyboardShortcuts: boolean;
}

export default function SettingsPage() {
  const { theme, setTheme, toggleTheme } = useThemeStore();
  const { sessions, clearAllSessions, getCurrentSession } = useSessionStore();

  const [preferences, setPreferences] = useState<UserPreferences>({
    responseLength: 'medium',
    autoSave: true,
    soundEnabled: false,
    animations: true,
    fontSize: 'medium',
    highContrast: false,
    reducedMotion: false,
    saveHistory: true,
    autoComplete: true,
    keyboardShortcuts: true
  });

  const [activeSection, setActiveSection] = useState<'appearance' | 'preferences' | 'data' | 'accessibility' | 'about'>('appearance');
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'checking'>('checking');

  const isTerminal = theme === 'terminal';

  // Load preferences from localStorage
  useEffect(() => {
    const savedPreferences = localStorage.getItem('ttrpg-user-preferences');
    if (savedPreferences) {
      try {
        setPreferences(JSON.parse(savedPreferences));
      } catch (error) {
        console.error('Failed to load preferences:', error);
      }
    }
  }, []);

  // Check API connection status
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch('http://localhost:8002/health');
        setConnectionStatus(response.ok ? 'connected' : 'disconnected');
      } catch (error) {
        setConnectionStatus('disconnected');
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const savePreferences = () => {
    localStorage.setItem('ttrpg-user-preferences', JSON.stringify(preferences));
    alert('Preferences saved successfully!');
  };

  const exportData = () => {
    const data = {
      sessions: sessions,
      preferences: preferences,
      theme: theme,
      exportDate: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ttrpg-center-data-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const clearAllData = () => {
    if (confirm('Are you sure you want to clear all data? This action cannot be undone.')) {
      clearAllSessions();
      localStorage.removeItem('ttrpg-user-preferences');
      localStorage.removeItem('ttrpg-theme-storage');
      setPreferences({
        responseLength: 'medium',
        autoSave: true,
        soundEnabled: false,
        animations: true,
        fontSize: 'medium',
        highContrast: false,
        reducedMotion: false,
        saveHistory: true,
        autoComplete: true,
        keyboardShortcuts: true
      });
      alert('All data cleared successfully!');
    }
  };

  const updatePreference = <K extends keyof UserPreferences>(
    key: K,
    value: UserPreferences[K]
  ) => {
    setPreferences(prev => ({ ...prev, [key]: value }));
  };

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return isTerminal ? 'text-terminal-text' : 'text-lcars-green';
      case 'disconnected': return isTerminal ? 'text-red-400' : 'text-lcars-red';
      case 'checking': return isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow';
      default: return isTerminal ? 'text-terminal-text/50' : 'text-white/50';
    }
  };

  const getConnectionStatusIcon = () => {
    switch (connectionStatus) {
      case 'connected': return <Activity className="h-4 w-4" />;
      case 'disconnected': return <Shield className="h-4 w-4" />;
      case 'checking': return <RefreshCw className="h-4 w-4 animate-spin" />;
      default: return <Database className="h-4 w-4" />;
    }
  };

  const navigationItems = [
    { id: 'appearance' as const, label: 'Appearance', icon: Palette },
    { id: 'preferences' as const, label: 'Preferences', icon: User },
    { id: 'data' as const, label: 'Data & Privacy', icon: Database },
    { id: 'accessibility' as const, label: 'Accessibility', icon: Accessibility },
    { id: 'about' as const, label: 'About', icon: Settings }
  ];

  return (
    <div className="h-full flex flex-col p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Settings className={`h-8 w-8 ${isTerminal ? 'text-terminal-text' : 'text-lcars-orange'}`} />
          <h1 className={`text-3xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
            {isTerminal ? 'SYSTEM_CONFIGURATION' : 'System Configuration'}
          </h1>
        </div>
        <p className={`${isTerminal ? 'text-terminal-text/70 font-mono' : 'text-white/70'}`}>
          {isTerminal ? 'Configure system parameters and user preferences.' : 'Customize your TTRPG Center experience'}
        </p>

        {/* Connection Status */}
        <div className={`
          inline-flex items-center gap-2 mt-4 px-3 py-1.5 rounded-lg text-sm
          ${isTerminal
            ? 'bg-terminal-text/5 border border-terminal-text/20'
            : 'bg-lcars-panel/20 border border-lcars-orange/30'
          }
        `}>
          <div className={getConnectionStatusColor()}>
            {getConnectionStatusIcon()}
          </div>
          <span className={getConnectionStatusColor()}>
            API Status: {connectionStatus.charAt(0).toUpperCase() + connectionStatus.slice(1)}
          </span>
        </div>
      </div>

      <div className="flex-1 flex gap-6">
        {/* Navigation Sidebar */}
        <div className={`
          w-64 space-y-2
          ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
          rounded-lg p-4
        `}>
          {navigationItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;

            return (
              <button
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                className={`
                  w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors
                  ${isActive
                    ? (isTerminal
                      ? 'bg-terminal-text/20 text-terminal-text'
                      : 'bg-lcars-orange/20 text-lcars-orange')
                    : (isTerminal
                      ? 'hover:bg-terminal-text/10 text-terminal-text/70 hover:text-terminal-text'
                      : 'hover:bg-white/10 text-white/70 hover:text-white')
                  }
                `}
              >
                <Icon className="h-4 w-4" />
                <span className={isTerminal ? 'font-mono' : ''}>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Content Area */}
        <div className="flex-1">
          {activeSection === 'appearance' && (
            <div className="space-y-6">
              <h2 className={`text-xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                Appearance Settings
              </h2>

              {/* Theme Selection */}
              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  Interface Theme
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <button
                    onClick={() => setTheme('terminal')}
                    className={`
                      p-4 rounded-lg border-2 transition-all
                      ${theme === 'terminal'
                        ? 'border-terminal-text bg-terminal-text/10'
                        : 'border-terminal-text/30 hover:border-terminal-text/50'
                      }
                    `}
                  >
                    <Terminal className="h-8 w-8 text-terminal-text mx-auto mb-2" />
                    <div className="text-terminal-text font-mono">TERMINAL</div>
                    <div className="text-terminal-text/70 text-sm font-mono">Retro computing interface</div>
                  </button>

                  <button
                    onClick={() => setTheme('lcars')}
                    className={`
                      p-4 rounded-lg border-2 transition-all
                      ${theme === 'lcars'
                        ? 'border-lcars-orange bg-lcars-orange/10'
                        : 'border-lcars-orange/30 hover:border-lcars-orange/50'
                      }
                    `}
                  >
                    <Monitor className="h-8 w-8 text-lcars-orange mx-auto mb-2" />
                    <div className="text-lcars-orange font-lcars">LCARS</div>
                    <div className="text-white/70 text-sm">Library Computer Access</div>
                  </button>
                </div>
              </div>

              {/* Font Size */}
              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  Font Size
                </h3>
                <div className="flex gap-2">
                  {(['small', 'medium', 'large'] as const).map((size) => (
                    <button
                      key={size}
                      onClick={() => updatePreference('fontSize', size)}
                      className={`
                        px-4 py-2 rounded-lg border transition-colors capitalize
                        ${preferences.fontSize === size
                          ? (isTerminal
                            ? 'border-terminal-text bg-terminal-text/20 text-terminal-text'
                            : 'border-lcars-orange bg-lcars-orange/20 text-lcars-orange')
                          : (isTerminal
                            ? 'border-terminal-text/30 text-terminal-text/70 hover:border-terminal-text/50'
                            : 'border-lcars-orange/30 text-white/70 hover:border-lcars-orange/50')
                        }
                      `}
                    >
                      {size}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === 'preferences' && (
            <div className="space-y-6">
              <h2 className={`text-xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                User Preferences
              </h2>

              {/* Response Settings */}
              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  Response Settings
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className={`block text-sm font-medium mb-2 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                      Default Response Length
                    </label>
                    <div className="flex gap-2">
                      {(['short', 'medium', 'long'] as const).map((length) => (
                        <button
                          key={length}
                          onClick={() => updatePreference('responseLength', length)}
                          className={`
                            px-3 py-1 rounded text-sm capitalize
                            ${preferences.responseLength === length
                              ? (isTerminal
                                ? 'bg-terminal-text/20 text-terminal-text border border-terminal-text'
                                : 'bg-lcars-orange/20 text-lcars-orange border border-lcars-orange')
                              : (isTerminal
                                ? 'bg-terminal-text/5 text-terminal-text/70 border border-terminal-text/30'
                                : 'bg-white/5 text-white/70 border border-white/30')
                            }
                          `}
                        >
                          {length}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Toggle Preferences */}
                  {[
                    { key: 'autoSave' as const, label: 'Auto-save conversations', icon: Save },
                    { key: 'soundEnabled' as const, label: 'Sound effects', icon: Volume2 },
                    { key: 'animations' as const, label: 'Interface animations', icon: Eye },
                    { key: 'autoComplete' as const, label: 'Query auto-completion', icon: Keyboard },
                    { key: 'keyboardShortcuts' as const, label: 'Keyboard shortcuts', icon: Keyboard }
                  ].map(({ key, label, icon: Icon }) => (
                    <div key={key} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Icon className={`h-4 w-4 ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`} />
                        <label className={`${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                          {label}
                        </label>
                      </div>
                      <button
                        onClick={() => updatePreference(key, !preferences[key] as any)}
                        className={`
                          w-12 h-6 rounded-full transition-colors relative
                          ${preferences[key]
                            ? (isTerminal ? 'bg-terminal-text' : 'bg-lcars-orange')
                            : (isTerminal ? 'bg-terminal-text/20' : 'bg-white/20')
                          }
                        `}
                      >
                        <div className={`
                          w-4 h-4 rounded-full bg-white transition-transform absolute top-1
                          ${preferences[key] ? 'translate-x-7' : 'translate-x-1'}
                        `} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === 'data' && (
            <div className="space-y-6">
              <h2 className={`text-xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                Data & Privacy
              </h2>

              {/* Data Management */}
              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  Data Management
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className={`font-medium ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                        Total Sessions: {sessions.length}
                      </div>
                      <div className={`text-sm ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                        Conversations stored locally
                      </div>
                    </div>
                  </div>

                  <div className="flex gap-4">
                    <button
                      onClick={exportData}
                      className={`
                        flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors
                        ${isTerminal
                          ? 'border-terminal-text/30 text-terminal-text hover:bg-terminal-text/10'
                          : 'border-lcars-orange/30 text-lcars-orange hover:bg-lcars-orange/10'
                        }
                      `}
                    >
                      <Download className="h-4 w-4" />
                      Export Data
                    </button>

                    <button
                      onClick={clearAllData}
                      className={`
                        flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors
                        ${isTerminal
                          ? 'border-red-400/30 text-red-400 hover:bg-red-400/10'
                          : 'border-lcars-red/30 text-lcars-red hover:bg-lcars-red/10'
                        }
                      `}
                    >
                      <Trash2 className="h-4 w-4" />
                      Clear All Data
                    </button>
                  </div>
                </div>
              </div>

              {/* Privacy Settings */}
              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  Privacy Settings
                </h3>
                <div className="flex items-center justify-between">
                  <div>
                    <div className={`font-medium ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                      Save Chat History
                    </div>
                    <div className={`text-sm ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                      Store conversations in browser storage
                    </div>
                  </div>
                  <button
                    onClick={() => updatePreference('saveHistory', !preferences.saveHistory)}
                    className={`
                      w-12 h-6 rounded-full transition-colors relative
                      ${preferences.saveHistory
                        ? (isTerminal ? 'bg-terminal-text' : 'bg-lcars-orange')
                        : (isTerminal ? 'bg-terminal-text/20' : 'bg-white/20')
                      }
                    `}
                  >
                    <div className={`
                      w-4 h-4 rounded-full bg-white transition-transform absolute top-1
                      ${preferences.saveHistory ? 'translate-x-7' : 'translate-x-1'}
                    `} />
                  </button>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'accessibility' && (
            <div className="space-y-6">
              <h2 className={`text-xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                Accessibility
              </h2>

              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  Visual Accessibility
                </h3>
                <div className="space-y-4">
                  {[
                    { key: 'highContrast' as const, label: 'High contrast mode', description: 'Increase contrast for better visibility' },
                    { key: 'reducedMotion' as const, label: 'Reduce motion', description: 'Minimize animations and transitions' }
                  ].map(({ key, label, description }) => (
                    <div key={key} className="flex items-center justify-between">
                      <div>
                        <div className={`font-medium ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                          {label}
                        </div>
                        <div className={`text-sm ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                          {description}
                        </div>
                      </div>
                      <button
                        onClick={() => updatePreference(key, !preferences[key] as any)}
                        className={`
                          w-12 h-6 rounded-full transition-colors relative
                          ${preferences[key]
                            ? (isTerminal ? 'bg-terminal-text' : 'bg-lcars-orange')
                            : (isTerminal ? 'bg-terminal-text/20' : 'bg-white/20')
                          }
                        `}
                      >
                        <div className={`
                          w-4 h-4 rounded-full bg-white transition-transform absolute top-1
                          ${preferences[key] ? 'translate-x-7' : 'translate-x-1'}
                        `} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeSection === 'about' && (
            <div className="space-y-6">
              <h2 className={`text-xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                About TTRPG Center
              </h2>

              <div className={`
                p-4 rounded-lg
                ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/10 border border-lcars-orange/30'}
              `}>
                <h3 className={`text-lg font-medium mb-4 ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                  System Information
                </h3>
                <div className="space-y-2">
                  <div className={`flex justify-between ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                    <span>Version:</span>
                    <span>2.0.0 MVP Enhanced</span>
                  </div>
                  <div className={`flex justify-between ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                    <span>Build:</span>
                    <span>{new Date().toISOString().split('T')[0]}</span>
                  </div>
                  <div className={`flex justify-between ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                    <span>Environment:</span>
                    <span>Development</span>
                  </div>
                  <div className={`flex justify-between ${isTerminal ? 'font-mono text-terminal-text' : 'text-white'}`}>
                    <span>API Status:</span>
                    <span className={getConnectionStatusColor()}>{connectionStatus}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Save Button */}
          <div className="mt-8 flex justify-end">
            <button
              onClick={savePreferences}
              className={`
                flex items-center gap-2 px-6 py-3 rounded-lg font-medium transition-colors
                ${isTerminal
                  ? 'bg-terminal-text/20 text-terminal-text hover:bg-terminal-text/30 border border-terminal-text/30'
                  : 'bg-lcars-orange text-black hover:bg-lcars-orange/90'
                }
              `}
            >
              <Save className="h-4 w-4" />
              Save Settings
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}