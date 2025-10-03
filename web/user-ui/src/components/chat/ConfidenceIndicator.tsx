/**
 * Confidence Indicator Component
 *
 * Visual indicator for AI response confidence and quality metrics
 */

import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface ConfidenceIndicatorProps {
  confidence: number;
  theme: 'terminal' | 'lcars';
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export default function ConfidenceIndicator({
  confidence,
  theme,
  size = 'sm',
  showLabel = false
}: ConfidenceIndicatorProps) {
  const isTerminal = theme === 'terminal';

  const getConfidenceLevel = () => {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.6) return 'medium';
    return 'low';
  };

  const getConfidenceColor = () => {
    const level = getConfidenceLevel();

    if (isTerminal) {
      switch (level) {
        case 'high': return 'text-terminal-text';
        case 'medium': return 'text-terminal-amber';
        case 'low': return 'text-red-400';
        default: return 'text-terminal-text/50';
      }
    } else {
      switch (level) {
        case 'high': return 'text-lcars-green';
        case 'medium': return 'text-lcars-yellow';
        case 'low': return 'text-lcars-red';
        default: return 'text-white/50';
      }
    }
  };

  const getConfidenceIcon = () => {
    const level = getConfidenceLevel();
    const iconSize = size === 'lg' ? 'h-4 w-4' : size === 'md' ? 'h-3.5 w-3.5' : 'h-3 w-3';

    switch (level) {
      case 'high': return <TrendingUp className={iconSize} />;
      case 'medium': return <Minus className={iconSize} />;
      case 'low': return <TrendingDown className={iconSize} />;
      default: return <Minus className={iconSize} />;
    }
  };

  const getBarWidth = () => {
    return Math.max(confidence * 100, 10); // Minimum 10% width for visibility
  };

  const textSize = size === 'lg' ? 'text-sm' : size === 'md' ? 'text-xs' : 'text-xs';

  return (
    <div className="flex items-center gap-2">
      {/* Icon */}
      <div className={getConfidenceColor()}>
        {getConfidenceIcon()}
      </div>

      {/* Progress Bar */}
      <div className={`
        ${size === 'lg' ? 'w-16 h-2' : size === 'md' ? 'w-12 h-1.5' : 'w-8 h-1'}
        ${isTerminal ? 'bg-terminal-text/20' : 'bg-white/20'}
        rounded-full overflow-hidden
      `}>
        <div
          className={`
            h-full transition-all duration-300 rounded-full
            ${getConfidenceColor().replace('text-', 'bg-')}
          `}
          style={{ width: `${getBarWidth()}%` }}
        />
      </div>

      {/* Label */}
      {showLabel && (
        <span className={`${textSize} ${getConfidenceColor()}`}>
          {Math.round(confidence * 100)}%
        </span>
      )}
    </div>
  );
}