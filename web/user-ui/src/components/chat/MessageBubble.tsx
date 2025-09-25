import React from 'react';
import { ChatMessage } from '../../stores/sessionStore';
import { Theme } from '../../stores/themeStore';
import { User, Bot, Play, Clock, CheckCircle, AlertCircle } from 'lucide-react';

interface MessageBubbleProps {
  message: ChatMessage;
  theme: Theme;
  onExecutePlan?: () => void;
}

export default function MessageBubble({ message, theme, onExecutePlan }: MessageBubbleProps) {
  const isTerminal = theme === 'terminal';
  const isUser = message.role === 'user';
  const isPlan = message.metadata?.type === 'plan';
  const isExecution = message.metadata?.type === 'execution';

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getConfidenceColor = (confidence?: number) => {
    if (!confidence) return isTerminal ? 'text-terminal-text/50' : 'text-white/50';
    if (confidence >= 0.8) return isTerminal ? 'text-terminal-text' : 'text-lcars-blue';
    if (confidence >= 0.6) return isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow';
    return isTerminal ? 'text-terminal-red' : 'text-lcars-red';
  };

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {/* Avatar */}
      {!isUser && (
        <div className={`
          flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${isTerminal
            ? 'bg-terminal-text/10 border border-terminal-text/30'
            : 'bg-lcars-orange'
          }
        `}>
          <Bot className={`h-4 w-4 ${isTerminal ? 'text-terminal-text' : 'text-black'}`} />
        </div>
      )}

      {/* Message Content */}
      <div className={`
        max-w-2xl response-card
        ${isUser
          ? isTerminal
            ? 'bg-terminal-text/10 border-terminal-text/30'
            : 'bg-lcars-blue/20 border-lcars-blue/30'
          : isTerminal
            ? 'bg-black/40 border-terminal-text/20'
            : 'bg-lcars-panel/20 border-lcars-orange/20'
        }
      `}>
        {/* Message Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className={`
              text-xs font-bold
              ${isUser
                ? isTerminal ? 'text-terminal-blue' : 'text-lcars-blue'
                : isTerminal ? 'text-terminal-amber' : 'text-lcars-orange'
              }
            `}>
              {isUser ? (isTerminal ? 'USER' : 'OPERATOR') : (isTerminal ? 'ASSISTANT' : 'COMPUTER')}
            </span>
            {isPlan && (
              <span className={`
                px-2 py-1 rounded text-xs font-bold
                ${isTerminal
                  ? 'bg-terminal-amber/20 text-terminal-amber'
                  : 'bg-lcars-blue/20 text-lcars-blue'
                }
              `}>
                PLAN
              </span>
            )}
            {isExecution && (
              <span className={`
                px-2 py-1 rounded text-xs font-bold
                ${isTerminal
                  ? 'bg-terminal-blue/20 text-terminal-blue'
                  : 'bg-lcars-red/20 text-lcars-red'
                }
              `}>
                EXECUTION
              </span>
            )}
          </div>
          <span className={`text-xs ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
            {formatTime(message.timestamp)}
          </span>
        </div>

        {/* Message Body */}
        <div className={`
          whitespace-pre-wrap leading-relaxed
          ${isTerminal ? 'font-mono text-sm' : 'font-lcars'}
          ${isUser
            ? isTerminal ? 'text-terminal-blue' : 'text-white'
            : isTerminal ? 'text-terminal-text' : 'text-white'
          }
        `}>
          {message.content}
        </div>

        {/* Plan Execution Button */}
        {isPlan && onExecutePlan && (
          <div className="mt-4 pt-3 border-t border-current/20">
            <button
              onClick={onExecutePlan}
              className={`
                flex items-center gap-2 px-4 py-2 rounded transition-all duration-200
                ${isTerminal
                  ? 'bg-terminal-blue/20 hover:bg-terminal-blue/30 text-terminal-blue border border-terminal-blue/30'
                  : 'lcars-button bg-lcars-blue hover:bg-lcars-blue/80'
                }
              `}
            >
              <Play className="h-4 w-4" />
              Execute Plan
            </button>
          </div>
        )}

        {/* Metadata Footer */}
        {(message.confidence !== undefined || message.sources?.length || message.metadata?.processingTime) && (
          <div className="mt-3 pt-3 border-t border-current/20 space-y-2">
            {/* Confidence */}
            {message.confidence !== undefined && (
              <div className="flex items-center gap-3">
                <span className={`text-xs ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                  Confidence:
                </span>
                <div className="flex-1 confidence-bar">
                  <div
                    className={`confidence-fill ${getConfidenceColor(message.confidence)}`}
                    style={{ width: `${message.confidence * 100}%` }}
                  />
                </div>
                <span className={`text-xs ${getConfidenceColor(message.confidence)}`}>
                  {Math.round(message.confidence * 100)}%
                </span>
              </div>
            )}

            {/* Sources */}
            {message.sources && message.sources.length > 0 && (
              <div className="flex flex-wrap gap-1">
                <span className={`text-xs ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                  Sources:
                </span>
                {message.sources.slice(0, 3).map((source, index) => (
                  <span
                    key={index}
                    className={`citation-badge ${isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'}`}
                  >
                    {source}
                  </span>
                ))}
                {message.sources.length > 3 && (
                  <span className={`citation-badge ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
                    +{message.sources.length - 3} more
                  </span>
                )}
              </div>
            )}

            {/* Processing Time */}
            {message.metadata?.processingTime && (
              <div className="flex items-center gap-2">
                <Clock className={`h-3 w-3 ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`} />
                <span className={`text-xs ${isTerminal ? 'text-terminal-text/70' : 'text-white/70'}`}>
                  {Math.round(message.metadata.processingTime)}ms
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className={`
          flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${isTerminal
            ? 'bg-terminal-blue/20 border border-terminal-blue/30'
            : 'bg-lcars-blue'
          }
        `}>
          <User className={`h-4 w-4 ${isTerminal ? 'text-terminal-blue' : 'text-white'}`} />
        </div>
      )}
    </div>
  );
}