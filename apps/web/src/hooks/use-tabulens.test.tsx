import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useUploadWorkbook, useJobResults } from './use-tabulens';
import { apiClient } from '@/lib/api-client';
import type { ReactNode } from 'react';

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    uploadWorkbook: vi.fn(),
    getJobRows: vi.fn(),
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

});
