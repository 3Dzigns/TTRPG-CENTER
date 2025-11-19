import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { Source } from '@ttrpg-center/types';
import { AdminSourceEditorDialog } from '../admin-source-editor-dialog';

const mockApi = {
  mutateAdminSource: vi.fn()
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

describe('AdminSourceEditorDialog', () => {
  const source: Source = {
    id: 'source-1',
    name: 'Player Handbook',
    category: 'ruleset',
    owned: false,
    updatedAt: new Date().toISOString()
  };

  it('submits updates with diff confirmation', async () => {
    mockApi.mutateAdminSource.mockResolvedValue({
      traceId: 'trace-123',
      action: 'update',
      source
    });
    const onCompleted = vi.fn();

    render(
      <AdminSourceEditorDialog
        open
        onOpenChange={() => {}}
        mode="edit"
        source={source}
        onCompleted={onCompleted}
      />,
      { wrapper }
    );

    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'Player Handbook Revised' } });
    fireEvent.click(screen.getByRole('button', { name: /review changes/i }));

    expect(await screen.findByText(/Before/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /confirm and save/i }));

    await waitFor(() => expect(mockApi.mutateAdminSource).toHaveBeenCalled());
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ traceId: 'trace-123', action: 'update' })
    );
  });

  it('can create a new source', async () => {
    mockApi.mutateAdminSource.mockResolvedValue({
      traceId: 'trace-create',
      action: 'create',
      source: { ...source, id: 'source-2', name: 'New Module' }
    });
    const onCompleted = vi.fn();

    render(
      <AdminSourceEditorDialog
        open
        onOpenChange={() => {}}
        mode="create"
        onCompleted={onCompleted}
      />,
      { wrapper }
    );

    fireEvent.change(screen.getByLabelText(/name/i), { target: { value: 'New Module' } });
    fireEvent.change(screen.getByLabelText(/category/i), { target: { value: 'module' } });
    fireEvent.click(screen.getByLabelText(/Owned/));
    fireEvent.click(screen.getByRole('button', { name: /review changes/i }));
    fireEvent.click(screen.getByRole('button', { name: /confirm and save/i }));

    await waitFor(() => expect(mockApi.mutateAdminSource).toHaveBeenCalled());
    expect(onCompleted).toHaveBeenCalledWith(
      expect.objectContaining({ traceId: 'trace-create', action: 'create' })
    );
  });
});
