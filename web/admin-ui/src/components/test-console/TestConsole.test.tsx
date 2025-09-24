/**
 * Test suite for Admin Test Console component
 *
 * Tests the external test execution functionality required by MVP v2
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import TestConsole from './TestConsole';

// Mock fetch globally
global.fetch = vi.fn();

// Mock EventSource
class MockEventSource {
  public onmessage: ((event: MessageEvent) => void) | null = null;
  public onerror: ((event: Event) => void) | null = null;
  public readyState: number = 1;

  constructor(public url: string) {}

  close() {
    this.readyState = 2;
  }

  dispatchEvent(event: Event): boolean {
    return true;
  }

  addEventListener() {}
  removeEventListener() {}
}

global.EventSource = MockEventSource as any;

describe('TestConsole', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders test console interface', () => {
    render(<TestConsole />);

    expect(screen.getByText('Test Console')).toBeInTheDocument();
    expect(screen.getByText('Execute Test Suite')).toBeInTheDocument();
    expect(screen.getByText('Test Suite')).toBeInTheDocument();
    expect(screen.getByText('Target Environment')).toBeInTheDocument();
  });

  it('displays all test suite options', () => {
    render(<TestConsole />);

    const suiteSelect = screen.getByRole('combobox', { name: /test suite/i });
    fireEvent.click(suiteSelect);

    expect(screen.getByText('Unit Tests')).toBeInTheDocument();
    expect(screen.getByText('Functional Tests')).toBeInTheDocument();
    expect(screen.getByText('Security Tests')).toBeInTheDocument();
    expect(screen.getByText('Regression Tests')).toBeInTheDocument();
    expect(screen.getByText('Performance Tests')).toBeInTheDocument();
  });

  it('displays all environment options', () => {
    render(<TestConsole />);

    const envSelect = screen.getByRole('combobox', { name: /target environment/i });
    fireEvent.click(envSelect);

    expect(screen.getByText('Development')).toBeInTheDocument();
    expect(screen.getByText('Testing')).toBeInTheDocument();
    expect(screen.getByText('Production')).toBeInTheDocument();
  });

  it('requires suite selection before execution', () => {
    render(<TestConsole />);

    const startButton = screen.getByRole('button', { name: /start test execution/i });
    expect(startButton).toBeDisabled();
  });

  it('enables execution button when suite is selected', async () => {
    render(<TestConsole />);

    // Select a test suite
    const suiteSelect = screen.getByRole('combobox', { name: /test suite/i });
    fireEvent.click(suiteSelect);
    fireEvent.click(screen.getByText('Unit Tests'));

    await waitFor(() => {
      const startButton = screen.getByRole('button', { name: /start test execution/i });
      expect(startButton).not.toBeDisabled();
    });
  });

  it('makes API call when execution starts', async () => {
    const mockResponse = {
      execution_id: 'test-123',
      suite_type: 'unit',
      target_environment: 'dev',
      status: 'queued',
      progress: 0,
      started_at: new Date().toISOString(),
      results_available: false
    };

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    render(<TestConsole />);

    // Select suite and environment
    const suiteSelect = screen.getByRole('combobox', { name: /test suite/i });
    fireEvent.click(suiteSelect);
    fireEvent.click(screen.getByText('Unit Tests'));

    // Start execution
    const startButton = screen.getByRole('button', { name: /start test execution/i });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8001/test/execute',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            suite_type: 'unit',
            target_environment: 'dev',
            timeout_minutes: 30
          })
        })
      );
    });
  });

  it('displays error message on API failure', async () => {
    (fetch as any).mockRejectedValueOnce(new Error('API Error'));

    // Mock alert
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});

    render(<TestConsole />);

    // Select suite
    const suiteSelect = screen.getByRole('combobox', { name: /test suite/i });
    fireEvent.click(suiteSelect);
    fireEvent.click(screen.getByText('Unit Tests'));

    // Start execution
    const startButton = screen.getByRole('button', { name: /start test execution/i });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText(/ERROR: API Error/)).toBeInTheDocument();
    });

    alertSpy.mockRestore();
  });

  it('shows stop button during execution', async () => {
    const mockResponse = {
      execution_id: 'test-123',
      suite_type: 'unit',
      target_environment: 'dev',
      status: 'running',
      progress: 0.5,
      started_at: new Date().toISOString(),
      results_available: false
    };

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    render(<TestConsole />);

    // Select suite
    const suiteSelect = screen.getByRole('combobox', { name: /test suite/i });
    fireEvent.click(suiteSelect);
    fireEvent.click(screen.getByText('Unit Tests'));

    // Start execution
    const startButton = screen.getByRole('button', { name: /start test execution/i });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
    });
  });

  it('loads existing executions on mount', async () => {
    const mockExecutions = [
      {
        execution_id: 'test-456',
        suite_type: 'functional',
        target_environment: 'test',
        status: 'completed',
        progress: 1.0,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        results_available: true
      }
    ];

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockExecutions
    });

    render(<TestConsole />);

    await waitFor(() => {
      expect(screen.getByText('Functional Tests')).toBeInTheDocument();
      expect(screen.getByText('completed')).toBeInTheDocument();
    });
  });

  it('allows downloading results for completed executions', async () => {
    const mockExecutions = [
      {
        execution_id: 'test-789',
        suite_type: 'unit',
        target_environment: 'dev',
        status: 'completed',
        progress: 1.0,
        started_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        results_available: true
      }
    ];

    (fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockExecutions
      })
      .mockResolvedValueOnce({
        ok: true,
        blob: async () => new Blob(['test results'], { type: 'application/json' })
      });

    // Mock URL.createObjectURL and related DOM methods
    const mockURL = {
      createObjectURL: vi.fn(() => 'mock-url'),
      revokeObjectURL: vi.fn()
    };
    Object.defineProperty(window, 'URL', { value: mockURL });

    const mockAnchor = {
      href: '',
      download: '',
      click: vi.fn()
    };
    const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor as any);
    const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockAnchor as any);
    const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => mockAnchor as any);

    render(<TestConsole />);

    await waitFor(() => {
      const downloadButton = screen.getByRole('button', { name: /results/i });
      fireEvent.click(downloadButton);
    });

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('http://localhost:8001/test/executions/test-789/results');
      expect(mockURL.createObjectURL).toHaveBeenCalled();
      expect(mockAnchor.click).toHaveBeenCalled();
    });

    createElementSpy.mockRestore();
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
  });

  it('updates timeout value correctly', () => {
    render(<TestConsole />);

    const timeoutInput = screen.getByRole('spinbutton', { name: /timeout/i });
    fireEvent.change(timeoutInput, { target: { value: '60' } });

    expect((timeoutInput as HTMLInputElement).value).toBe('60');
  });

  it('updates test filter correctly', () => {
    render(<TestConsole />);

    const filterInput = screen.getByRole('textbox', { name: /test filter/i });
    fireEvent.change(filterInput, { target: { value: 'test_basic*' } });

    expect((filterInput as HTMLInputElement).value).toBe('test_basic*');
  });
});

describe('TestConsole Integration', () => {
  it('handles complete test execution workflow', async () => {
    const mockExecution = {
      execution_id: 'workflow-test',
      suite_type: 'unit',
      target_environment: 'dev',
      status: 'queued',
      progress: 0,
      started_at: new Date().toISOString(),
      results_available: false
    };

    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockExecution
    });

    render(<TestConsole />);

    // Select test suite
    const suiteSelect = screen.getByRole('combobox', { name: /test suite/i });
    fireEvent.click(suiteSelect);
    fireEvent.click(screen.getByText('Unit Tests'));

    // Start execution
    const startButton = screen.getByRole('button', { name: /start test execution/i });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText('Test Output')).toBeInTheDocument();
      expect(screen.getByText('queued')).toBeInTheDocument();
    });
  });
});