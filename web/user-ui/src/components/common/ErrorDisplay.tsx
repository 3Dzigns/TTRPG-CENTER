/**
 * Error Display Component
 *
 * Displays user-friendly error messages with appropriate actions
 */

import React from 'react';
import { AlertTriangle, RefreshCw, X, Info } from 'lucide-react';
import { UserFriendlyError } from '../../utils/errorHandler';

interface ErrorDisplayProps {
  error: UserFriendlyError;
  onRetry?: () => void;
  onDismiss?: () => void;
  theme?: 'terminal' | 'lcars';
  size?: 'sm' | 'md' | 'lg';
  showTechnical?: boolean;
}

export default function ErrorDisplay({
  error,
  onRetry,
  onDismiss,
  theme = 'terminal',
  size = 'md',
  showTechnical = false
}: ErrorDisplayProps) {
  const isTerminal = theme === 'terminal';

  const sizeClasses = {
    sm: 'p-3 text-sm',
    md: 'p-4 text-base',
    lg: 'p-6 text-lg'
  };

  const iconSize = {
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
    lg: 'h-6 w-6'
  };

  return (
    <div className={`
      ${sizeClasses[size]} rounded-lg border
      ${isTerminal
        ? 'bg-red-900/20 border-red-500/30 text-red-300'
        : 'bg-red-900/30 border-lcars-red/50 text-red-200'
      }
    `}>
      <div className="flex items-start gap-3">
        {/* Error Icon */}
        <AlertTriangle className={`${iconSize[size]} text-red-400 flex-shrink-0 mt-0.5`} />

        {/* Error Content */}
        <div className="flex-1 min-w-0">
          <h3 className={`
            font-semibold mb-1
            ${isTerminal ? 'text-red-300' : 'text-red-200'}
          `}>
            {error.title}
          </h3>

          <p className={`
            mb-2
            ${isTerminal ? 'text-red-200/80' : 'text-red-100/80'}
          `}>
            {error.message}
          </p>

          {error.action && (
            <p className={`
              text-sm mb-3
              ${isTerminal ? 'text-red-300/60' : 'text-red-200/60'}
            `}>
              <Info className="h-3 w-3 inline mr-1" />
              {error.action}
            </p>
          )}

          {/* Technical Details (Development/Debug) */}
          {showTechnical && error.technical && (
            <details className="mt-3">
              <summary className={`
                text-xs cursor-pointer mb-2
                ${isTerminal ? 'text-red-400/70' : 'text-red-300/70'}
              `}>
                Technical Details
              </summary>
              <pre className={`
                text-xs p-2 rounded overflow-auto max-h-32
                ${isTerminal
                  ? 'bg-black/50 text-red-300/80 border border-red-500/20'
                  : 'bg-black/40 text-red-200/80 border border-lcars-red/30'
                }
              `}>
                {error.technical}
              </pre>
            </details>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 mt-3">
            {error.retryable && onRetry && (
              <button
                onClick={onRetry}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors
                  ${isTerminal
                    ? 'bg-red-600/20 hover:bg-red-600/30 text-red-300 border border-red-500/30'
                    : 'bg-lcars-red/20 hover:bg-lcars-red/30 text-red-200 border border-lcars-red/40'
                  }
                `}
              >
                <RefreshCw className="h-3 w-3" />
                Try Again
              </button>
            )}

            {onDismiss && (
              <button
                onClick={onDismiss}
                className={`
                  flex items-center gap-1.5 px-3 py-1.5 text-xs rounded transition-colors
                  ${isTerminal
                    ? 'bg-gray-600/20 hover:bg-gray-600/30 text-gray-300 border border-gray-500/30'
                    : 'bg-gray-600/20 hover:bg-gray-600/30 text-gray-200 border border-gray-500/40'
                  }
                `}
              >
                <X className="h-3 w-3" />
                Dismiss
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}