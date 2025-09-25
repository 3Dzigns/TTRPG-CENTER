import React, { useState, useEffect, useRef } from 'react';
import { useThemeStore } from '../stores/themeStore';
import { useSessionStore } from '../stores/sessionStore';
import { Send, Loader2, Sparkles, Brain, Play } from 'lucide-react';
import MessageBubble from '../components/chat/MessageBubble';
import { useUserAPI } from '../hooks/useUserAPI';

export default function ChatPage() {
  const { theme } = useThemeStore();
  const {
    currentSessionId,
    createSession,
    addMessage,
    getCurrentSession
  } = useSessionStore();

  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { askQuery, createPlan, executePlan } = useUserAPI();
  const currentSession = getCurrentSession();

  // Create session if none exists
  useEffect(() => {
    if (!currentSessionId) {
      createSession('New Chat Session');
    }
  }, [currentSessionId, createSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentSession?.messages]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId) return;

    const userMessage = {
      role: 'user' as const,
      content: input.trim()
    };

    // Add user message
    addMessage(currentSessionId, userMessage);
    setInput('');
    setIsProcessing(true);

    try {
      // Determine if this is a planning request
      const isPlanRequest = input.toLowerCase().includes('plan') ||
                          input.toLowerCase().includes('workflow') ||
                          input.toLowerCase().includes('step');

      if (isPlanRequest) {
        // Use plan endpoint
        const planResponse = await createPlan({
          request: input.trim(),
          session_id: currentSessionId
        });

        const assistantMessage = {
          role: 'assistant' as const,
          content: `I've created a ${planResponse.steps.length}-step plan for you:\n\n${planResponse.steps.map((step, i) =>
            `${i + 1}. ${step.description} (${step.estimated_duration_seconds}s)`
          ).join('\n')}\n\nTotal estimated time: ${Math.ceil(planResponse.total_estimated_duration_seconds / 60)} minutes\n\nWould you like me to execute this plan?`,
          metadata: {
            type: 'plan',
            planId: planResponse.plan_id,
            steps: planResponse.steps
          }
        };

        addMessage(currentSessionId, assistantMessage);
      } else {
        // Use ask endpoint
        const response = await askQuery({
          query: input.trim(),
          session_id: currentSessionId
        });

        const assistantMessage = {
          role: 'assistant' as const,
          content: response.answer,
          confidence: response.confidence,
          sources: response.sources,
          metadata: {
            type: 'answer',
            processingTime: response.processing_time_ms,
            classification: response.classification
          }
        };

        addMessage(currentSessionId, assistantMessage);
      }
    } catch (error) {
      console.error('Failed to process message:', error);
      const errorMessage = {
        role: 'assistant' as const,
        content: 'I apologize, but I encountered an error processing your request. Please try again.',
        metadata: { type: 'error' }
      };
      addMessage(currentSessionId, errorMessage);
    } finally {
      setIsProcessing(false);
      inputRef.current?.focus();
    }
  };

  const handleExecutePlan = async (planId: string) => {
    if (!currentSessionId) return;

    setIsProcessing(true);
    try {
      const execution = await executePlan({
        plan_id: planId,
        session_id: currentSessionId,
        execute_all: true
      });

      const message = {
        role: 'assistant' as const,
        content: `Plan execution started! Run ID: ${execution.run_id}\n\nStatus: ${execution.status}\nProgress: ${Math.round(execution.progress * 100)}%`,
        metadata: {
          type: 'execution',
          runId: execution.run_id,
          planId: planId
        }
      };

      addMessage(currentSessionId, message);
    } catch (error) {
      console.error('Failed to execute plan:', error);
      const errorMessage = {
        role: 'assistant' as const,
        content: 'Failed to execute the plan. Please try again.',
        metadata: { type: 'error' }
      };
      addMessage(currentSessionId, errorMessage);
    } finally {
      setIsProcessing(false);
    }
  };

  const isTerminal = theme === 'terminal';

  return (
    <div className="h-full flex flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!currentSession?.messages.length && (
          <div className={`text-center py-12 ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
            <div className={`text-6xl mb-4 ${isTerminal ? 'text-terminal-text' : 'text-lcars-orange'}`}>
              {isTerminal ? '>' : '●'}
            </div>
            <h2 className={`text-2xl font-bold mb-2 ${isTerminal ? 'font-mono' : 'font-lcars'}`}>
              {isTerminal ? 'TTRPG_CENTER_READY' : 'COMMUNICATION CHANNEL OPEN'}
            </h2>
            <p className="text-sm mb-6">
              {isTerminal
                ? 'Enter your query at the command prompt. System ready for natural language processing.'
                : 'Ready to assist with your TTRPG queries and workflow planning.'
              }
            </p>
            <div className={`text-xs ${isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'}`}>
              Try: "What is armor class in D&D?" or "Plan a character creation workflow"
            </div>
          </div>
        )}

        {currentSession?.messages.map((message, index) => (
          <MessageBubble
            key={message.id}
            message={message}
            theme={theme}
            onExecutePlan={message.metadata?.planId ? () => handleExecutePlan(message.metadata.planId) : undefined}
          />
        ))}

        {isProcessing && (
          <div className={`flex items-center gap-3 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'}`}>
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className={isTerminal ? 'font-mono' : 'font-lcars'}>
              {isTerminal ? 'PROCESSING_QUERY...' : 'Processing request...'}
            </span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className={`p-4 border-t ${isTerminal ? 'border-terminal-text/20 bg-black/30' : 'border-lcars-orange bg-lcars-panel/10'}`}>
        <form onSubmit={handleSubmit} className="flex gap-3">
          <div className="flex-1 relative">
            {isTerminal && (
              <div className="absolute left-3 top-1/2 -translate-y-1/2 text-terminal-text font-mono">
                {'> '}
              </div>
            )}
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className={
                isTerminal
                  ? 'terminal-input pl-8 w-full py-3 px-4 border border-terminal-text/30 rounded-md bg-black/50 focus:border-terminal-text focus:outline-none'
                  : 'lcars-input w-full'
              }
              placeholder={isTerminal ? 'Enter command or query...' : 'Enter your request...'}
              disabled={isProcessing}
            />
          </div>

          <button
            type="submit"
            disabled={!input.trim() || isProcessing}
            className={
              isTerminal
                ? 'px-6 py-3 bg-terminal-text/10 border border-terminal-text/30 rounded-md text-terminal-text hover:bg-terminal-text/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-mono'
                : 'lcars-button disabled:opacity-50 disabled:cursor-not-allowed'
            }
          >
            <Send className="h-4 w-4" />
          </button>
        </form>

        {/* Quick Actions */}
        <div className="flex gap-2 mt-3">
          <button
            onClick={() => setInput('What are the basic rules of D&D combat?')}
            className={`
              flex items-center gap-2 px-3 py-1 rounded text-xs transition-colors
              ${isTerminal
                ? 'bg-terminal-text/5 hover:bg-terminal-text/10 text-terminal-text/70 hover:text-terminal-text border border-terminal-text/20'
                : 'bg-lcars-orange/20 hover:bg-lcars-orange/30 text-lcars-orange'
              }
            `}
          >
            <Sparkles className="h-3 w-3" />
            Ask about rules
          </button>

          <button
            onClick={() => setInput('Plan a character creation workflow for a new D&D player')}
            className={`
              flex items-center gap-2 px-3 py-1 rounded text-xs transition-colors
              ${isTerminal
                ? 'bg-terminal-text/5 hover:bg-terminal-text/10 text-terminal-text/70 hover:text-terminal-text border border-terminal-text/20'
                : 'bg-lcars-blue/20 hover:bg-lcars-blue/30 text-lcars-blue'
              }
            `}
          >
            <Brain className="h-3 w-3" />
            Plan workflow
          </button>
        </div>
      </div>
    </div>
  );
}