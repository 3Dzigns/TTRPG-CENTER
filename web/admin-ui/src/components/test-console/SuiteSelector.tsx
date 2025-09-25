/**
 * Test Suite Selector Component
 *
 * Handles test suite and environment selection with timeout configuration
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { PlayCircle, Square, RefreshCw, Terminal } from 'lucide-react';

interface SuiteSelectorProps {
  selectedSuite: string;
  selectedEnvironment: string;
  testFilter: string;
  timeoutMinutes: number;
  isExecuting: boolean;
  onSuiteChange: (value: string) => void;
  onEnvironmentChange: (value: string) => void;
  onTestFilterChange: (value: string) => void;
  onTimeoutChange: (value: number) => void;
  onStartExecution: () => void;
  onStopExecution: () => void;
  onRefresh: () => void;
}

const SUITE_TYPES = [
  { value: 'unit', label: 'Unit Tests', description: 'Fast, isolated component tests' },
  { value: 'functional', label: 'Functional Tests', description: 'API and UI workflow tests' },
  { value: 'security', label: 'Security Tests', description: 'SAST/DAST and vulnerability scans' },
  { value: 'regression', label: 'Regression Tests', description: 'Golden snapshots and eval sets' },
  { value: 'performance', label: 'Performance Tests', description: 'Load testing and benchmarks' }
];

const ENVIRONMENTS = [
  { value: 'dev', label: 'Development', description: 'Local development environment' },
  { value: 'test', label: 'Testing', description: 'Staging environment for QA' },
  { value: 'prod', label: 'Production', description: 'Live production environment' }
];

export default function SuiteSelector({
  selectedSuite,
  selectedEnvironment,
  testFilter,
  timeoutMinutes,
  isExecuting,
  onSuiteChange,
  onEnvironmentChange,
  onTestFilterChange,
  onTimeoutChange,
  onStartExecution,
  onStopExecution,
  onRefresh
}: SuiteSelectorProps) {
  return (
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
            <Select value={selectedSuite} onValueChange={onSuiteChange}>
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
            <Select value={selectedEnvironment} onValueChange={onEnvironmentChange}>
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
              onChange={(e) => onTestFilterChange(e.target.value)}
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
              onChange={(e) => onTimeoutChange(parseInt(e.target.value) || 30)}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <Button
            onClick={onStartExecution}
            disabled={isExecuting || !selectedSuite}
            className="flex items-center gap-2"
          >
            <PlayCircle className="h-4 w-4" />
            Start Test Execution
          </Button>

          {isExecuting && (
            <Button
              variant="destructive"
              onClick={onStopExecution}
              className="flex items-center gap-2"
            >
              <Square className="h-4 w-4" />
              Stop
            </Button>
          )}

          <Button
            variant="outline"
            onClick={onRefresh}
            className="flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}