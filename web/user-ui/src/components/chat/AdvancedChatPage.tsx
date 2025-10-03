/**
 * Advanced Chat Page Component
 *
 * Enhanced chat interface with intent-aware processing, real-time streaming,
 * advanced query understanding, and comprehensive UI components
 */

import React, { useState, useEffect, useRef } from 'react';
import { useThemeStore } from '../../stores/themeStore';
import { useSessionStore } from '../../stores/sessionStore';
import {
  Send,
  Loader2,
  Sparkles,
  Brain,
  Play,
  Search,
  Zap,
  Clock,
  Target,
  BookOpen,
  Wand2,
  Code,
  FileText,
  Network,
  TrendingUp,
  MessageSquare,
  Star,
  History,
  Settings
} from 'lucide-react';
import MessageBubble from './MessageBubble';
import QuerySuggestions from './QuerySuggestions';
import IntentClassifier from './IntentClassifier';
import StreamingIndicator from './StreamingIndicator';
import ConfidenceIndicator from './ConfidenceIndicator';
import { useUserAPI } from '../../hooks/useUserAPI';
import { handleApiError } from '../../utils/errorHandler';
import ErrorDisplay from '../common/ErrorDisplay';

interface QueryContext {
  intent: 'fact_lookup' | 'procedural_howto' | 'creative_write' | 'code_help' | 'summarize' | 'multi_hop_reasoning' | 'planning';
  confidence: number;
  domain: string;
  complexity: 'simple' | 'moderate' | 'complex';
  suggestedModel: string;
}

interface ProcessingState {
  phase: 'classifying' | 'retrieving' | 'generating' | 'complete';
  progress: number;
  currentStep: string;
  estimatedTime?: number;
}

export default function AdvancedChatPage() {
  const { theme } = useThemeStore();
  const {
    currentSessionId,
    createSession,
    addMessage,
    getCurrentSession
  } = useSessionStore();

  // Input and processing state
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingState, setProcessingState] = useState<ProcessingState | null>(null);
  const [queryContext, setQueryContext] = useState<QueryContext | null>(null);

  // Advanced features
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const [quickActions, setQuickActions] = useState<string[]>([]);
  const [currentError, setCurrentError] = useState<any>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const streamingTimeoutRef = useRef<NodeJS.Timeout>();

  const { askQuery, createPlan, executePlan } = useUserAPI();
  const currentSession = getCurrentSession();
  const isTerminal = theme === 'terminal';

  // Initialize session
  useEffect(() => {
    if (!currentSessionId) {
      createSession('Advanced Chat Session');
    }
  }, [currentSessionId, createSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [currentSession?.messages, streamingContent]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Load quick actions based on session history
  useEffect(() => {
    const loadQuickActions = () => {
      const commonActions = [
        'What are the basic rules of D&D combat?',
        'How do I create a character in Pathfinder?',
        'Explain spell slots and spellcasting',
        'What dice do I need for RPGs?',
        'How to be a good dungeon master?',
        'Plan a character creation workflow',
        'Create a session 0 checklist',
        'Design a custom magic item'
      ];
      setQuickActions(commonActions);
    };

    loadQuickActions();
  }, [currentSession]);

  // Intent classification
  const classifyQuery = async (query: string): Promise<QueryContext> => {
    // Mock intent classification - in real app this would call the QIC service
    const keywords = query.toLowerCase();

    let intent: QueryContext['intent'] = 'fact_lookup';
    let domain = 'general';
    let complexity: QueryContext['complexity'] = 'simple';

    if (keywords.includes('how') || keywords.includes('tutorial') || keywords.includes('guide')) {
      intent = 'procedural_howto';
      complexity = 'moderate';
    } else if (keywords.includes('create') || keywords.includes('write') || keywords.includes('design')) {
      intent = 'creative_write';
      complexity = 'complex';
    } else if (keywords.includes('code') || keywords.includes('api') || keywords.includes('programming')) {
      intent = 'code_help';
      domain = 'technical';
    } else if (keywords.includes('summarize') || keywords.includes('explain') || keywords.includes('what is')) {
      intent = 'summarize';
    } else if (keywords.includes('plan') || keywords.includes('workflow') || keywords.includes('step')) {
      intent = 'planning';
      complexity = 'complex';
    } else if (keywords.includes('because') || keywords.includes('why') || keywords.includes('relationship')) {
      intent = 'multi_hop_reasoning';
      complexity = 'complex';
    }

    // Determine domain
    if (keywords.includes('d&d') || keywords.includes('dnd') || keywords.includes('dungeons')) {
      domain = 'dnd5e';
    } else if (keywords.includes('pathfinder')) {
      domain = 'pathfinder';
    } else if (keywords.includes('character') || keywords.includes('spell') || keywords.includes('combat')) {
      domain = 'ttrpg';
    }

    const confidence = Math.random() * 0.3 + 0.7; // Mock confidence 70-100%
    const modelMap = {
      simple: 'gpt-4o-mini',
      moderate: 'gpt-4o',
      complex: 'gpt-4o-large'
    };

    return {
      intent,
      confidence,
      domain,
      complexity,
      suggestedModel: modelMap[complexity]
    };
  };

  // Simulate real-time streaming
  const simulateStreaming = (content: string, onComplete: () => void) => {
    setIsStreaming(true);
    setStreamingContent('');

    let index = 0;
    const words = content.split(' ');

    const streamNextWord = () => {
      if (index < words.length) {
        setStreamingContent(prev => prev + (index > 0 ? ' ' : '') + words[index]);
        index++;
        streamingTimeoutRef.current = setTimeout(streamNextWord, 50 + Math.random() * 100);
      } else {
        setIsStreaming(false);
        onComplete();
      }
    };

    streamNextWord();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId || isProcessing) return;

    const queryText = input.trim();
    setInput('');
    setIsProcessing(true);
    setShowSuggestions(false);

    // Add user message
    const userMessage = {
      role: 'user' as const,
      content: queryText
    };
    addMessage(currentSessionId, userMessage);

    try {
      // Phase 1: Intent Classification
      setProcessingState({
        phase: 'classifying',
        progress: 10,
        currentStep: 'Analyzing query intent...'
      });

      const context = await classifyQuery(queryText);
      setQueryContext(context);

      // Phase 2: Retrieval Planning
      setProcessingState({
        phase: 'retrieving',
        progress: 30,
        currentStep: `Retrieving ${context.domain} information...`,
        estimatedTime: context.complexity === 'complex' ? 15 : 8
      });

      // Simulate retrieval delay
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Phase 3: Response Generation
      setProcessingState({
        phase: 'generating',
        progress: 60,
        currentStep: `Generating response with ${context.suggestedModel}...`
      });

      let response;
      if (context.intent === 'planning') {
        // Use plan endpoint
        response = await createPlan({
          request: queryText,
          session_id: currentSessionId,
          complexity_limit: context.complexity
        });

        const planContent = `I've created a ${response.steps.length}-step ${context.complexity} plan for you:\n\n${response.steps.map((step, i) =>
          `**Step ${i + 1}:** ${step.description}\n*Estimated time:* ${step.estimated_duration_seconds}s\n*Dependencies:* ${step.dependencies.join(', ') || 'None'}\n`
        ).join('\n')}\n**Total estimated time:** ${Math.ceil(response.total_estimated_duration_seconds / 60)} minutes\n\nWould you like me to execute this plan?`;

        // Complete processing
        setProcessingState({
          phase: 'complete',
          progress: 100,
          currentStep: 'Plan generated successfully'
        });

        // Stream the response
        simulateStreaming(planContent, () => {
          const assistantMessage = {
            role: 'assistant' as const,
            content: planContent,
            metadata: {
              type: 'plan',
              planId: response.plan_id,
              steps: response.steps,
              intent: context.intent,
              confidence: context.confidence,
              complexity: context.complexity,
              model: context.suggestedModel
            }
          };
          addMessage(currentSessionId, assistantMessage);
          setStreamingContent('');
          setProcessingState(null);
          setQueryContext(null);
        });

      } else {
        // Use ask endpoint
        response = await askQuery({
          query: queryText,
          session_id: currentSessionId
        });

        // Complete processing
        setProcessingState({
          phase: 'complete',
          progress: 100,
          currentStep: 'Response generated successfully'
        });

        // Stream the response
        simulateStreaming(response.answer, () => {
          const assistantMessage = {
            role: 'assistant' as const,
            content: response.answer,
            confidence: response.confidence,
            sources: response.sources,
            metadata: {
              type: 'answer',
              processingTime: response.processing_time_ms,
              classification: response.classification,
              intent: context.intent,
              complexity: context.complexity,
              model: context.suggestedModel
            }
          };
          addMessage(currentSessionId, assistantMessage);
          setStreamingContent('');
          setProcessingState(null);
          setQueryContext(null);
        });
      }

    } catch (error) {
      console.error('Failed to process message:', error);
      setIsStreaming(false);
      setStreamingContent('');

      // Handle API errors with user-friendly messages
      const userError = handleApiError(error);
      setCurrentError(userError);

      const errorMessage = {
        role: 'assistant' as const,
        content: `${userError.title}: ${userError.message}`,
        metadata: {
          type: 'error',
          retryable: userError.retryable,
          technical: userError.technical
        }
      };
      addMessage(currentSessionId, errorMessage);

      setProcessingState(null);
      setQueryContext(null);
    } finally {
      setIsProcessing(false);
      inputRef.current?.focus();
    }
  };

  const handleQuickAction = (action: string) => {
    setInput(action);
    setShowSuggestions(false);
    inputRef.current?.focus();
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
        content: `🚀 **Plan Execution Started**\n\n**Run ID:** ${execution.run_id}\n**Status:** ${execution.status}\n**Progress:** ${Math.round(execution.progress * 100)}%\n\nI'll update you as each step completes.`,
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

  const getIntentIcon = (intent: string) => {
    switch (intent) {
      case 'fact_lookup': return <Search className="h-4 w-4" />;
      case 'procedural_howto': return <BookOpen className="h-4 w-4" />;
      case 'creative_write': return <Wand2 className="h-4 w-4" />;
      case 'code_help': return <Code className="h-4 w-4" />;
      case 'summarize': return <FileText className="h-4 w-4" />;
      case 'multi_hop_reasoning': return <Network className="h-4 w-4" />;
      case 'planning': return <Brain className="h-4 w-4" />;
      default: return <MessageSquare className="h-4 w-4" />;
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Enhanced Header with Status */}
      <div className={`p-4 border-b ${isTerminal ? 'border-terminal-text/20 bg-black/20' : 'border-lcars-orange bg-lcars-panel/10'}`}>
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className={`${isTerminal ? 'text-terminal-text' : 'text-lcars-orange'}`}>
              <MessageSquare className="h-5 w-5" />
            </div>
            <div>
              <h2 className={`font-medium ${isTerminal ? 'font-mono text-terminal-text' : 'font-lcars text-white'}`}>
                {currentSession?.name || 'Chat Session'}
              </h2>
              <div className={`text-xs ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                {currentSession?.messages.length || 0} messages • Advanced mode enabled
              </div>
            </div>
          </div>

          {/* Status Indicators */}
          <div className="flex items-center gap-2">
            {queryContext && (
              <div className={`flex items-center gap-2 px-2 py-1 rounded text-xs ${isTerminal ? 'bg-terminal-text/10 text-terminal-text' : 'bg-lcars-blue/20 text-lcars-blue'}`}>
                {getIntentIcon(queryContext.intent)}
                <span>{queryContext.intent.replace('_', ' ')}</span>
                <ConfidenceIndicator confidence={queryContext.confidence} theme={theme} />
              </div>
            )}

            <div className={`w-2 h-2 rounded-full ${isProcessing || isStreaming ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`} />
          </div>
        </div>

        {/* Processing State */}
        {processingState && (
          <div className="mt-3">
            <div className={`text-xs mb-2 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'}`}>
              {processingState.currentStep}
            </div>
            <div className={`w-full rounded-full h-1 ${isTerminal ? 'bg-terminal-text/20' : 'bg-white/20'}`}>
              <div
                className={`h-1 rounded-full transition-all duration-300 ${isTerminal ? 'bg-terminal-amber' : 'bg-lcars-yellow'}`}
                style={{ width: `${processingState.progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {!currentSession?.messages.length && (
          <div className={`text-center py-12 ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
            <div className={`text-6xl mb-4 ${isTerminal ? 'text-terminal-text' : 'text-lcars-orange'}`}>
              {isTerminal ? '◆' : '●'}
            </div>
            <h2 className={`text-2xl font-bold mb-2 ${isTerminal ? 'font-mono' : 'font-lcars'}`}>
              {isTerminal ? 'ADVANCED_QUERY_INTERFACE' : 'ENHANCED COMMUNICATION READY'}
            </h2>
            <p className="text-sm mb-6">
              {isTerminal
                ? 'Advanced query processing with intent classification and real-time streaming enabled.'
                : 'AI-powered assistant with advanced query understanding and workflow planning.'
              }
            </p>
            <div className={`text-xs mb-4 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'}`}>
              ✨ Intent-aware processing • 🔄 Real-time streaming • 🧠 Workflow planning
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

        {/* Streaming Message */}
        {isStreaming && streamingContent && (
          <div className={`${isTerminal ? 'text-terminal-text' : 'text-white'}`}>
            <div className={`inline-block p-3 rounded-lg max-w-3xl ${isTerminal ? 'bg-terminal-text/5 border border-terminal-text/20' : 'bg-lcars-panel/20'}`}>
              <div className="flex items-start gap-2 mb-2">
                <Zap className={`h-4 w-4 mt-0.5 ${isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'}`} />
                <span className="text-xs opacity-70">Streaming response...</span>
              </div>
              <div className="prose prose-sm max-w-none">
                {streamingContent}
                <span className={`inline-block w-2 h-4 ml-1 animate-pulse ${isTerminal ? 'bg-terminal-amber' : 'bg-lcars-yellow'}`} />
              </div>
            </div>
          </div>
        )}

        {/* Error Display */}
        {currentError && (
          <ErrorDisplay
            error={currentError}
            theme={theme}
            onRetry={() => {
              setCurrentError(null);
              // Retry the last query if it was retryable
              if (currentError.retryable && input.trim()) {
                handleSubmit(new Event('submit') as any);
              }
            }}
            onDismiss={() => setCurrentError(null)}
            showTechnical={process.env.NODE_ENV === 'development'}
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Enhanced Input Area */}
      <div className={`p-4 border-t ${isTerminal ? 'border-terminal-text/20 bg-black/30' : 'border-lcars-orange bg-lcars-panel/10'}`}>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1 relative">
              {isTerminal && (
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-terminal-text font-mono">
                  {'◆ '}
                </div>
              )}
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  setShowSuggestions(e.target.value.length > 2);
                }}
                className={
                  isTerminal
                    ? 'terminal-input pl-8 w-full py-3 px-4 border border-terminal-text/30 rounded-md bg-black/50 focus:border-terminal-text focus:outline-none font-mono'
                    : 'lcars-input w-full'
                }
                placeholder={isTerminal ? 'Enter advanced query or command...' : 'Ask anything about TTRPGs...'}
                disabled={isProcessing || isStreaming}
              />

              {/* Query Suggestions */}
              {showSuggestions && input.length > 2 && (
                <QuerySuggestions
                  query={input}
                  onSelect={handleQuickAction}
                  theme={theme}
                />
              )}
            </div>

            <button
              type="submit"
              disabled={!input.trim() || isProcessing || isStreaming}
              className={
                isTerminal
                  ? 'px-6 py-3 bg-terminal-text/10 border border-terminal-text/30 rounded-md text-terminal-text hover:bg-terminal-text/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-mono'
                  : 'lcars-button disabled:opacity-50 disabled:cursor-not-allowed'
              }
            >
              <Send className="h-4 w-4" />
            </button>
          </div>

          {/* Enhanced Quick Actions */}
          <div className="flex flex-wrap gap-2">
            {quickActions.slice(0, 4).map((action, index) => {
              const icons = [Sparkles, Brain, BookOpen, Wand2];
              const Icon = icons[index] || MessageSquare;

              return (
                <button
                  key={index}
                  onClick={() => handleQuickAction(action)}
                  className={`
                    flex items-center gap-2 px-3 py-1 rounded text-xs transition-colors
                    ${isTerminal
                      ? 'bg-terminal-text/5 hover:bg-terminal-text/10 text-terminal-text/70 hover:text-terminal-text border border-terminal-text/20'
                      : 'bg-lcars-orange/20 hover:bg-lcars-orange/30 text-lcars-orange'
                    }
                  `}
                  disabled={isProcessing || isStreaming}
                >
                  <Icon className="h-3 w-3" />
                  {action.slice(0, 25)}...
                </button>
              );
            })}
          </div>
        </form>
      </div>
    </div>
  );
}