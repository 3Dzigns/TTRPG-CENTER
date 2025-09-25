import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  confidence?: number;
  sources?: string[];
  citations?: Array<{ source: string; label: string; passage?: string }>;
  metadata?: Record<string, any>;
}

export interface Session {
  id: string;
  name: string;
  messages: ChatMessage[];
  createdAt: Date;
  lastActivity: Date;
}

interface SessionState {
  currentSessionId: string | null;
  sessions: Session[];
  createSession: (name?: string) => string;
  setCurrentSession: (sessionId: string) => void;
  addMessage: (sessionId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  clearSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  getCurrentSession: () => Session | null;
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      currentSessionId: null,
      sessions: [],

      createSession: (name?: string) => {
        const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const newSession: Session = {
          id: sessionId,
          name: name || `Session ${new Date().toLocaleDateString()}`,
          messages: [],
          createdAt: new Date(),
          lastActivity: new Date()
        };

        set(state => ({
          sessions: [...state.sessions, newSession],
          currentSessionId: sessionId
        }));

        return sessionId;
      },

      setCurrentSession: (sessionId: string) => {
        set({ currentSessionId: sessionId });
      },

      addMessage: (sessionId: string, message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
        const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const fullMessage: ChatMessage = {
          ...message,
          id: messageId,
          timestamp: new Date()
        };

        set(state => ({
          sessions: state.sessions.map(session =>
            session.id === sessionId
              ? {
                  ...session,
                  messages: [...session.messages, fullMessage],
                  lastActivity: new Date()
                }
              : session
          )
        }));
      },

      clearSession: (sessionId: string) => {
        set(state => ({
          sessions: state.sessions.map(session =>
            session.id === sessionId
              ? { ...session, messages: [] }
              : session
          )
        }));
      },

      deleteSession: (sessionId: string) => {
        set(state => {
          const newSessions = state.sessions.filter(s => s.id !== sessionId);
          return {
            sessions: newSessions,
            currentSessionId: state.currentSessionId === sessionId
              ? (newSessions.length > 0 ? newSessions[0].id : null)
              : state.currentSessionId
          };
        });
      },

      getCurrentSession: () => {
        const state = get();
        return state.sessions.find(s => s.id === state.currentSessionId) || null;
      }
    }),
    {
      name: 'ttrpg-session-storage',
    }
  )
);