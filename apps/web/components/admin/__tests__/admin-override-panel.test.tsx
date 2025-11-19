import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { AdminOverridePanel } from '../admin-override-panel';

const mockApi = {
  submitAdminOverride: vi.fn()
};

vi.mock('../../../lib/api', () => ({
  getApiClient: () => mockApi
}));

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
};

describe('AdminOverridePanel', () => {
  it('validates JSON payload', async () => {
    mockApi.submitAdminOverride.mockResolvedValue({ traceId: 'trace-override', status: 'accepted' });
    const handleCompleted = vi.fn();

    render(<AdminOverridePanel onCompleted={handleCompleted} />, { wrapper });

    fireEvent.change(screen.getByLabelText(/Record path/i), { target: { value: 'ks.table/id' } });
    fireEvent.change(screen.getByLabelText(/JSON payload/i), { target: { value: 'not-json' } });
    fireEvent.change(screen.getByLabelText(/Reason/i), { target: { value: 'Fix record' } });
    fireEvent.click(screen.getByRole('button', { name: /submit override/i }));

    expect(await screen.findByText(/Payload must be valid JSON/i)).toBeInTheDocument();
    expect(mockApi.submitAdminOverride).not.toHaveBeenCalled();
  });

  it('submits override and surfaces trace id', async () => {
    mockApi.submitAdminOverride.mockResolvedValue({ traceId: 'trace-override', status: 'accepted' });
    const handleCompleted = vi.fn();

    render(<AdminOverridePanel onCompleted={handleCompleted} />, { wrapper });

    fireEvent.change(screen.getByLabelText(/Record path/i), { target: { value: 'ks.table/id' } });
    fireEvent.change(screen.getByLabelText(/JSON payload/i), {
      target: { value: '{"foo":"bar"}' }
    });
    fireEvent.change(screen.getByLabelText(/Reason/i), { target: { value: 'Fix record' } });
    fireEvent.click(screen.getByRole('button', { name: /submit override/i }));

    await waitFor(() => expect(mockApi.submitAdminOverride).toHaveBeenCalled());
    expect(handleCompleted).toHaveBeenCalledWith(
      { traceId: 'trace-override', status: 'accepted' },
      'cassandra',
      undefined
    );
    expect(screen.getByText(/Trace ID: trace-override/i)).toBeInTheDocument();
  });
});
