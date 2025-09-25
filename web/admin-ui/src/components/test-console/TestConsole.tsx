/**
 * Admin Test Console - External Test Execution
 *
 * MVP v2 requirement: Admin UI can launch Unit/Functional/Security/Regression/Perf
 * test runs against any environment and stream results.
 *
 * Refactored into smaller, reusable components with shared state management.
 */

import React from 'react';
import SuiteSelector from './SuiteSelector';
import LogStream from './LogStream';
import ExecutionList from './ExecutionList';
import ArtifactViewer from './ArtifactViewer';
import { useTestConsole } from './useTestConsole';

export default function TestConsole() {
  const {
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
  } = useTestConsole();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Test Console</h1>
        <p className="text-muted-foreground">
          Execute external test suites against any environment and monitor results in real-time
        </p>
      </div>

      {/* Test Execution Form - Now as separate component */}
      <SuiteSelector
        selectedSuite={selectedSuite}
        selectedEnvironment={selectedEnvironment}
        testFilter={testFilter}
        timeoutMinutes={timeoutMinutes}
        isExecuting={isExecuting}
        onSuiteChange={setSelectedSuite}
        onEnvironmentChange={setSelectedEnvironment}
        onTestFilterChange={setTestFilter}
        onTimeoutChange={setTimeoutMinutes}
        onStartExecution={startTestExecution}
        onStopExecution={stopTestExecution}
        onRefresh={loadTestExecutions}
      />

      {/* Real-time Output Stream - Now as separate component */}
      <LogStream
        isExecuting={isExecuting}
        streamOutput={streamOutput}
        activeExecution={activeExecution}
      />

      {/* Execution History - Now as separate component */}
      <ExecutionList
        executions={executions}
        onDownloadResults={downloadResults}
      />

      {/* Test Artifacts Viewer - New component */}
      <ArtifactViewer
        selectedExecutionId={activeExecution?.execution_id}
      />
    </div>
  );
}