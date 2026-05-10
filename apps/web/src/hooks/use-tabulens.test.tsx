import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useUploadWorkbook, useJobResults, useApplyProposal, useDiscardProposal } from './use-tabulens';
import { apiClient } from '@/lib/api-client';
import type { ReactNode } from 'react';

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    uploadWorkbook: vi.fn(),
    getJobRows: vi.fn(),
    applyProposal: vi.fn(),
    discardProposal: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('use-tabulens hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('useUploadWorkbook works', async () => {
    const mockData = { workbook_id: '123' };
    (apiClient.uploadWorkbook as any).mockResolvedValue(mockData);

    const { result } = renderHook(() => useUploadWorkbook(), { wrapper: createWrapper() });
    
    result.current.mutate(new File([], 'test.csv'));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockData);
  });

  it('useJobResults works', async () => {
    const mockRows = [{ id: 1 }];
    (apiClient.getJobRows as any).mockResolvedValue(mockRows);

    const { result } = renderHook(() => useJobResults('job-123'), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(mockRows);
  });

  it('useApplyProposal works', async () => {
    (apiClient.applyProposal as any).mockResolvedValue({} as any);
    const { result } = renderHook(() => useApplyProposal('job-123'), { wrapper: createWrapper() });
    
    await result.current.mutateAsync('prop-1');
    expect(apiClient.applyProposal).toHaveBeenCalledWith('job-123', 'prop-1');
  });

  it('useDiscardProposal works', async () => {
    (apiClient.discardProposal as any).mockResolvedValue({} as any);
    const { result } = renderHook(() => useDiscardProposal('job-123'), { wrapper: createWrapper() });
    
    await result.current.mutateAsync('prop-1');
    expect(apiClient.discardProposal).toHaveBeenCalledWith('job-123', 'prop-1');
  });
});
