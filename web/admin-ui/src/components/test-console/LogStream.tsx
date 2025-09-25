/**
 * Log Stream Component
 *
 * Real-time test execution output streaming
 */

import React, { useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { RefreshCw } from 'lucide-react';

interface TestExecution {
  execution_id: string;
  suite_type: string;
  target_environment: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  progress: number;
  current_test?: string;
  results_available: boolean;
}

interface LogStreamProps {
  isExecuting: boolean;
  streamOutput: string[];
  activeExecution: TestExecution | null;
}

export default function LogStream({ isExecuting, streamOutput, activeExecution }: LogStreamProps) {
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll output to bottom
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [streamOutput]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'running': return 'bg-blue-100 text-blue-800';
      default: return 'bg-yellow-100 text-yellow-800';
    }
  };

  if (!isExecuting && streamOutput.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Test Output</span>
          {activeExecution && (
            <div className="flex items-center gap-2">
              <Badge className={getStatusColor(activeExecution.status)}>
                {activeExecution.status}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {Math.round(activeExecution.progress * 100)}%
              </span>
            </div>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-96 w-full border rounded-md p-4">
          <div ref={outputRef} className="font-mono text-sm space-y-1">
            {streamOutput.map((line, index) => (
              <div key={index} className="whitespace-pre-wrap">
                {line}
              </div>
            ))}
            {isExecuting && (
              <div className="flex items-center gap-2 text-muted-foreground">
                <RefreshCw className="h-3 w-3 animate-spin" />
                Executing...
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Progress Bar for Active Execution */}
        {activeExecution && activeExecution.status === 'running' && (
          <div className="mt-4 space-y-2">
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Progress</span>
              <span>{Math.round(activeExecution.progress * 100)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${activeExecution.progress * 100}%` }}
              />
            </div>
            {activeExecution.current_test && (
              <div className="text-xs text-muted-foreground">
                Running: {activeExecution.current_test}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}