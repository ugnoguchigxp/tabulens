import { useMutation, useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export function useUploadWorkbook() {
  return useMutation({
    mutationFn: (file: File) => apiClient.uploadWorkbook(file),
  });
}

export function useRunAnalysis() {
  return useMutation({
    mutationFn: (payload: any) => apiClient.runAnalysis(payload),
  });
}

export function useRunModelWorkflow() {
  return useMutation({
    mutationFn: (payload: any) => apiClient.runModelWorkflow(payload),
  });
}

export function useRunExploration() {
  return useMutation({
    mutationFn: (payload: any) => apiClient.runExploration(payload),
  });
}

export function useJobResults(jobId: string | null) {
  return useQuery({
    queryKey: ['job-results', jobId],
    queryFn: () => apiClient.getJobRows(jobId!),
    enabled: !!jobId,
  });
}

export function useJobBoundary(jobId: string | null) {
  return useQuery({
    queryKey: ['job-boundary', jobId],
    queryFn: () => apiClient.getJobBoundary(jobId!),
    enabled: !!jobId,
    retry: false,
  });
}

export function useWorkflowBoundary(workflowId: string | null, enabled = true) {
  return useQuery({
    queryKey: ['workflow-boundary', workflowId],
    queryFn: () => apiClient.getModelWorkflowBoundary(workflowId!),
    enabled: !!workflowId && enabled,
    retry: false,
  });
}
