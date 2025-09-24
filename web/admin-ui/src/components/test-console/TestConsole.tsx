/**
 * Admin Test Console - External Test Execution
 *
 * MVP v2 requirement: Admin UI can launch Unit/Functional/Security/Regression/Perf
 * test runs against any environment and stream results.
 */

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  PlayCircle,
  Square,
  RefreshCw,
  Download,
  AlertCircle,
  CheckCircle,
  Clock,
  Terminal
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

interface TestSuiteRequest {
  suite_type: string;
  target_environment: string;
  test_filter?: string;
  timeout_minutes?: number;
}

const SUITE_TYPES = [
  { value: 'unit', label: 'Unit Tests', description: 'Fast, isolated component tests' },
  { value: 'functional', label: 'Functional Tests', description: 'API and UI workflow tests' },
  { value: 'security', label: 'Security Tests', description: 'SAST/DAST and vulnerability scans' },
  { value: 'regression', label: 'Regression Tests', description: 'Golden snapshots and eval sets' },
  { value: 'perf', label: 'Performance Tests', description: 'Load testing and benchmarks' }
];

const ENVIRONMENTS = [
  { value: 'dev', label: 'Development', description: 'Local development environment' },
  { value: 'test', label: 'Testing', description: 'Staging environment for QA' },
  { value: 'prod', label: 'Production', description: 'Live production environment' }
];

export default function TestConsole() {
  const [executions, setExecutions] = useState<TestExecution[]>([]);
  const [selectedSuite, setSelectedSuite] = useState<string>('');
  const [selectedEnvironment, setSelectedEnvironment] = useState<string>('dev');
  const [testFilter, setTestFilter] = useState<string>('');
  const [timeoutMinutes, setTimeoutMinutes] = useState<number>(30);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [streamOutput, setStreamOutput] = useState<string[]>([]);
  const [activeExecution, setActiveExecution] = useState<TestExecution | null>(null);

  const outputRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Load existing executions on mount
    loadTestExecutions();

    // Cleanup on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  useEffect(() => {
    // Auto-scroll output to bottom
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [streamOutput]);

  const loadTestExecutions = async () => {
    try {
      // Get admin API URL from environment config
      const adminApiUrl = getAdminApiUrl();
      const response = await fetch(`${adminApiUrl}/test/executions`);

      if (response.ok) {
        const data = await response.json();
        setExecutions(data);
      }
    } catch (error) {
      console.error('Failed to load test executions:', error);
    }
  };

  const startTestExecution = async () => {
    if (!selectedSuite || !selectedEnvironment) {
      alert('Please select both test suite and target environment');
      return;
    }

    setIsExecuting(true);
    setStreamOutput([]);

    try {
      const adminApiUrl = getAdminApiUrl();
      const request: TestSuiteRequest = {
        suite_type: selectedSuite,
        target_environment: selectedEnvironment,
        test_filter: testFilter || undefined,
        timeout_minutes: timeoutMinutes
      };

      const response = await fetch(`${adminApiUrl}/test/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`Test execution failed: ${response.statusText}`);
      }

      const execution: TestExecution = await response.json();
      setActiveExecution(execution);
      setExecutions(prev => [execution, ...prev]);

      // Start streaming output
      startOutputStream(execution.execution_id);

    } catch (error) {
      console.error('Failed to start test execution:', error);
      setStreamOutput(prev => [...prev, `ERROR: ${error.message}`]);
      setIsExecuting(false);
    }
  };

  const startOutputStream = (executionId: string) => {
    const adminApiUrl = getAdminApiUrl();
    const streamUrl = `${adminApiUrl}/test/executions/${executionId}/stream`;

    // Close existing stream
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const eventSource = new EventSource(streamUrl);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.line) {
          setStreamOutput(prev => [...prev, data.line]);
        }

        if (data.progress) {
          setActiveExecution(prev => prev ? {
            ...prev,
            progress: data.progress
          } : null);
        }

        if (data.status === 'completed' || data.status === 'failed') {
          setIsExecuting(false);
          setActiveExecution(prev => prev ? {
            ...prev,
            status: data.status,
            progress: 1.0,
            completed_at: new Date().toISOString(),
            results_available: true
          } : null);

          eventSource.close();
          loadTestExecutions(); // Refresh the list
        }
      } catch (error) {
        console.error('Error parsing stream data:', error);
      }
    };

    eventSource.onerror = (error) => {
      console.error('Stream error:', error);
      setStreamOutput(prev => [...prev, 'ERROR: Stream connection lost']);
      setIsExecuting(false);
      eventSource.close();
    };
  };

  const stopTestExecution = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    setIsExecuting(false);
    setStreamOutput(prev => [...prev, 'Test execution stopped by user']);
  };

  const downloadResults = async (executionId: string) => {
    try {
      const adminApiUrl = getAdminApiUrl();
      const response = await fetch(`${adminApiUrl}/test/executions/${executionId}/results`);

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `test-results-${executionId}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Failed to download results:', error);
    }
  };

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

  const getAdminApiUrl = (): string => {
    // In a real implementation, this would come from environment configuration
    const currentEnv = process.env.NODE_ENV || 'development';
    const portMap = {
      development: 8001,
      test: 8182,
      production: 8283
    };
    const port = portMap[currentEnv] || 8001;
    return `http://localhost:${port}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Test Console</h1>
        <p className="text-muted-foreground">
          Execute external test suites against any environment and monitor results in real-time
        </p>
      </div>

      {/* Test Execution Form */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Execute Test Suite
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="suite-select">Test Suite</Label>
              <Select value={selectedSuite} onValueChange={setSelectedSuite}>
                <SelectTrigger>
                  <SelectValue placeholder="Select test suite" />
                </SelectTrigger>
                <SelectContent>
                  {SUITE_TYPES.map(suite => (
                    <SelectItem key={suite.value} value={suite.value}>
                      <div>
                        <div className="font-medium">{suite.label}</div>
                        <div className="text-sm text-muted-foreground">{suite.description}</div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="env-select">Target Environment</Label>
              <Select value={selectedEnvironment} onValueChange={setSelectedEnvironment}>
                <SelectTrigger>
                  <SelectValue placeholder="Select environment" />
                </SelectTrigger>
                <SelectContent>
                  {ENVIRONMENTS.map(env => (
                    <SelectItem key={env.value} value={env.value}>
                      <div>
                        <div className="font-medium">{env.label}</div>
                        <div className="text-sm text-muted-foreground">{env.description}</div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="test-filter">Test Filter (Optional)</Label>
              <Input
                id="test-filter"
                placeholder="e.g., test_basic*, TestClass"
                value={testFilter}
                onChange={(e) => setTestFilter(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="timeout">Timeout (Minutes)</Label>
              <Input
                id="timeout"
                type="number"
                min="1"
                max="120"
                value={timeoutMinutes}
                onChange={(e) => setTimeoutMinutes(parseInt(e.target.value) || 30)}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              onClick={startTestExecution}
              disabled={isExecuting || !selectedSuite}
              className="flex items-center gap-2"
            >
              <PlayCircle className="h-4 w-4" />
              Start Test Execution
            </Button>

            {isExecuting && (
              <Button
                variant="destructive"
                onClick={stopTestExecution}
                className="flex items-center gap-2"
              >
                <Square className="h-4 w-4" />
                Stop
              </Button>
            )}

            <Button
              variant="outline"
              onClick={loadTestExecutions}
              className="flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Real-time Output */}
      {(isExecuting || streamOutput.length > 0) && (
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
          </CardContent>
        </Card>
      )}

      {/* Execution History */}
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
                          onClick={() => downloadResults(execution.execution_id)}
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
    </div>
  );
}