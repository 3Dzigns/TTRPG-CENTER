/**
 * Streaming Indicator Component
 *
 * Visual indicator for real-time response streaming
 */

import React from 'react';
import { Zap, Radio, Activity } from 'lucide-react';

interface StreamingIndicatorProps {
  isStreaming: boolean;
  theme: 'terminal' | 'lcars';
  phase?: 'connecting' | 'streaming' | 'complete';
  wordsPerSecond?: number;
}

export default function StreamingIndicator({
  isStreaming,
  theme,
  phase = 'streaming',
  wordsPerSecond = 0
}: StreamingIndicatorProps) {
  const isTerminal = theme === 'terminal';

  if (!isStreaming && phase !== 'complete') {
    return null;
  }

  const getPhaseInfo = () => {
    switch (phase) {
      case 'connecting':
        return {
          icon: Radio,
          label: isTerminal ? 'ESTABLISHING_CONNECTION' : 'Connecting to AI model...',
          color: isTerminal ? 'text-terminal-amber' : 'text-lcars-yellow'
        };
      case 'streaming':
        return {
          icon: Zap,
          label: isTerminal ? 'STREAMING_RESPONSE' : 'Receiving response...',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-green'
        };
      case 'complete':
        return {
          icon: Activity,
          label: isTerminal ? 'TRANSMISSION_COMPLETE' : 'Response complete',
          color: isTerminal ? 'text-terminal-text' : 'text-lcars-blue'
        };
      default:
        return {
          icon: Activity,
          label: isTerminal ? 'PROCESSING' : 'Processing...',
          color: isTerminal ? 'text-terminal-text/70' : 'text-white/70'
        };
    }
  };

  const phaseInfo = getPhaseInfo();
  const Icon = phaseInfo.icon;

  return (
    <div className={`
      inline-flex items-center gap-2 px-2 py-1 rounded text-xs
      ${isTerminal
        ? 'bg-terminal-text/5 border border-terminal-text/20'
        : 'bg-lcars-panel/20 border border-lcars-orange/30'
      }
    `}>
      {/* Icon with animation */}
      <div className={phaseInfo.color}>
        {isStreaming ? (
          <Icon className="h-3 w-3 animate-pulse" />
        ) : (
          <Icon className="h-3 w-3" />
        )}
      </div>

      {/* Status text */}
      <span className={`${phaseInfo.color} font-mono text-xs`}>
        {phaseInfo.label}
      </span>

      {/* Words per second indicator */}
      {isStreaming && wordsPerSecond > 0 && (
        <>
          <div className={`w-px h-3 ${isTerminal ? 'bg-terminal-text/20' : 'bg-white/20'}`} />
          <span className={`text-xs ${isTerminal ? 'text-terminal-text/50' : 'text-white/50'}`}>
            {wordsPerSecond.toFixed(1)} w/s
          </span>
        </>
      )}

      {/* Animated dots for terminal theme */}
      {isStreaming && isTerminal && (
        <div className="flex gap-0.5">
          <div className="w-1 h-1 bg-terminal-amber rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-1 h-1 bg-terminal-amber rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-1 h-1 bg-terminal-amber rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      )}

      {/* LCARS-style streaming indicator */}
      {isStreaming && !isTerminal && (
        <div className="flex items-center gap-1">
          <div className="w-2 h-2 bg-lcars-orange rounded-full animate-pulse" />
          <div className="w-1 h-1 bg-lcars-orange rounded-full animate-pulse" style={{ animationDelay: '0.5s' }} />
        </div>
      )}
    </div>
  );
}