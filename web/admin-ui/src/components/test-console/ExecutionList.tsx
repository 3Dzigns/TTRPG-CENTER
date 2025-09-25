/**
 * Execution List Component
 *
 * Display test execution history with status and download capabilities
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Clock,
  Download
} from 'lucide-react';

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

interface ExecutionListProps {
  executions: TestExecution[];
  onDownloadResults: (executionId: string) => void;
}

const SUITE_TYPES = [
  { value: 'unit', label: 'Unit Tests' },
  { value: 'functional', label: 'Functional Tests' },
  { value: 'security', label: 'Security Tests' },
  { value: 'regression', label: 'Regression Tests' },
  { value: 'performance', label: 'Performance Tests' }
];

export default function ExecutionList({ executions, onDownloadResults }: ExecutionListProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      case 'running':
        return <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="h-4 w-4 text-yellow-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'bg-green-100 text-green-800';
      case 'failed': return 'bg-red-100 text-red-800';
      case 'running': return 'bg-blue-100 text-blue-800';
      default: return 'bg-yellow-100 text-yellow-800';
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Test Execution History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {executions.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No test executions found. Start your first test above.
            </p>
          ) : (
            executions.map((execution) => (
              <div key={execution.execution_id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(execution.status)}
                    <div>
                      <div className="font-medium">
                        {SUITE_TYPES.find(s => s.value === execution.suite_type)?.label || execution.suite_type}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Target: {execution.target_environment} • {execution.execution_id.slice(0, 8)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={getStatusColor(execution.status)}>
                      {execution.status}
                    </Badge>
                    {execution.results_available && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onDownloadResults(execution.execution_id)}
                        className="flex items-center gap-1"
                      >
                        <Download className="h-3 w-3" />
                        Results
                      </Button>
                    )}
                  </div>
                </div>

                {execution.progress > 0 && execution.status === 'running' && (
                  <div className="mt-2">
                    <div className="flex justify-between text-sm text-muted-foreground mb-1">
                      <span>Progress</span>
                      <span>{Math.round(execution.progress * 100)}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${execution.progress * 100}%` }}
                      />
                    </div>
                    {execution.current_test && (
                      <div className="text-xs text-muted-foreground mt-1">
                        Running: {execution.current_test}
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                  <span>Started: {execution.started_at ? new Date(execution.started_at).toLocaleString() : 'N/A'}</span>
                  {execution.completed_at && (
                    <span>Completed: {new Date(execution.completed_at).toLocaleString()}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}