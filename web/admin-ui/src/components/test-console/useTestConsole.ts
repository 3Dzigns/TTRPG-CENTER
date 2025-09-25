/**
 * Test Console Hook
 *
 * Shared state management for test execution and streaming
 */

import { useState, useEffect, useRef } from 'react';

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

export function useTestConsole() {
  // Form state
  const [selectedSuite, setSelectedSuite] = useState<string>('');
  const [selectedEnvironment, setSelectedEnvironment] = useState<string>('dev');
  const [testFilter, setTestFilter] = useState<string>('');
  const [timeoutMinutes, setTimeoutMinutes] = useState<number>(30);

  // Execution state
  const [executions, setExecutions] = useState<TestExecution[]>([]);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [activeExecution, setActiveExecution] = useState<TestExecution | null>(null);

  // Streaming state
  const [streamOutput, setStreamOutput] = useState<string[]>([]);
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

  const getAdminApiUrl = (): string => {
    const currentEnv = process.env.NODE_ENV || 'development';
    const portMap = {
      development: 8001,
      test: 8182,
      production: 8283
    };
    const port = portMap[currentEnv] || 8001;
    return `http://localhost:${port}`;
  };

  const loadTestExecutions = async () => {
    try {
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

  return {
    // Form state
    selectedSuite,
    setSelectedSuite,
    selectedEnvironment,
    setSelectedEnvironment,
    testFilter,
    setTestFilter,
    timeoutMinutes,
    setTimeoutMinutes,

    // Execution state
    executions,
    isExecuting,
    activeExecution,

    // Streaming state
    streamOutput,

    // Actions
    startTestExecution,
    stopTestExecution,
    loadTestExecutions,
    downloadResults
  };
}