import React from 'react';
import { useThemeStore } from '../stores/themeStore';
import { useSessionStore } from '../stores/sessionStore';
import { History, Trash2, MessageCircle, Calendar, Clock } from 'lucide-react';

export default function HistoryPage() {
  const { theme } = useThemeStore();
  const { sessions, setCurrentSession, deleteSession } = useSessionStore();
  const isTerminal = theme === 'terminal';

  const formatDate = (date: Date) => {
    return new Date(date).toLocaleDateString([], {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const sortedSessions = sessions.sort((a, b) =>
    new Date(b.lastActivity).getTime() - new Date(a.lastActivity).getTime()
  );

  return (
    <div className="h-full p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className={`mb-8 ${isTerminal ? 'text-terminal-text' : 'text-white'}`}>
          <div className="flex items-center gap-3 mb-4">
            <History className={`h-8 w-8 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-orange'}`} />
            <h1 className={`text-3xl font-bold ${isTerminal ? 'font-mono' : 'font-lcars'}`}>
              {isTerminal ? 'SESSION_HISTORY' : 'COMMUNICATION RECORDS'}
            </h1>
          </div>
          <p className={`${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
            {isTerminal
              ? 'Access and manage previous conversation sessions'
              : 'Review past interactions and session data'
            }
          </p>
        </div>

        {/* Sessions List */}
        <div className="space-y-4">
          {sortedSessions.length === 0 ? (
            <div className={`
              text-center py-16
              ${isTerminal
                ? 'border-2 border-dashed border-terminal-text/20 bg-black/20'
                : 'border-2 border-dashed border-lcars-orange/30 bg-lcars-panel/10'
              }
            `}>
              <History className={`h-16 w-16 mx-auto mb-4 ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`} />
              <h3 className={`text-xl font-bold mb-2 ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
                {isTerminal ? 'NO_SESSIONS_FOUND' : 'No Session Records'}
              </h3>
              <p className={`${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
                Start a conversation to create your first session
              </p>
            </div>
          ) : (
            sortedSessions.map((session) => (
              <div
                key={session.id}
                className={`
                  response-card cursor-pointer transition-all duration-200 group
                  ${isTerminal
                    ? 'hover:bg-terminal-text/10 border-terminal-text/20'
                    : 'hover:bg-lcars-panel/30 border-lcars-orange/20'
                  }
                `}
                onClick={() => setCurrentSession(session.id)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    {/* Session Info */}
                    <div className="flex items-center gap-3 mb-2">
                      <MessageCircle className={`h-5 w-5 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-orange'}`} />
                      <h3 className={`font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
                        {session.name}
                      </h3>
                      <span className={`
                        px-2 py-1 rounded text-xs font-bold
                        ${isTerminal
                          ? 'bg-terminal-blue/20 text-terminal-blue'
                          : 'bg-lcars-blue/20 text-lcars-blue'
                        }
                      `}>
                        {session.messages.length} messages
                      </span>
                    </div>

                    {/* Session Metadata */}
                    <div className="flex items-center gap-4 text-xs">
                      <div className={`flex items-center gap-1 ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                        <Calendar className="h-3 w-3" />
                        Created: {formatDate(session.createdAt)}
                      </div>
                      <div className={`flex items-center gap-1 ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                        <Clock className="h-3 w-3" />
                        Last activity: {formatTime(session.lastActivity)}
                      </div>
                    </div>

                    {/* Preview of last message */}
                    {session.messages.length > 0 && (
                      <div className="mt-3">
                        <div className={`
                          text-sm line-clamp-2
                          ${isTerminal ? 'text-terminal-text/80 font-mono' : 'text-white/80 font-lcars'}
                        `}>
                          {session.messages[session.messages.length - 1].content.substring(0, 150)}
                          {session.messages[session.messages.length - 1].content.length > 150 ? '...' : ''}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Delete session "${session.name}"?`)) {
                          deleteSession(session.id);
                        }
                      }}
                      className={`
                        p-2 rounded transition-colors opacity-0 group-hover:opacity-100
                        ${isTerminal
                          ? 'hover:bg-terminal-red/20 text-terminal-red'
                          : 'hover:bg-lcars-red/20 text-lcars-red'
                        }
                      `}
                      title="Delete session"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Stats */}
        {sessions.length > 0 && (
          <div className={`
            mt-8 p-4 rounded-lg
            ${isTerminal
              ? 'bg-terminal-text/5 border border-terminal-text/20'
              : 'bg-lcars-panel/20 border border-lcars-orange/20'
            }
          `}>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className={`text-2xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
                  {sessions.length}
                </div>
                <div className={`text-xs ${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
                  {isTerminal ? 'SESSIONS' : 'Sessions'}
                </div>
              </div>
              <div>
                <div className={`text-2xl font-bold ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
                  {sessions.reduce((total, session) => total + session.messages.length, 0)}
                </div>
                <div className={`text-xs ${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
                  {isTerminal ? 'MESSAGES' : 'Messages'}
                </div>
              </div>
              <div>
                <div className={`text-2xl font-bold ${isTerminal ? 'font-mono text-terminal-amber' : 'font-lcars text-lcars-orange'}`}>
                  {sessions.filter(s => s.messages.length > 0).length}
                </div>
                <div className={`text-xs ${isTerminal ? 'font-mono text-terminal-text/70' : 'font-lcars text-white/70'}`}>
                  {isTerminal ? 'ACTIVE' : 'Active'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}