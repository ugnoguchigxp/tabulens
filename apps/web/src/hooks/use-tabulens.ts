import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

const invalidateJobQueries = (queryClient: ReturnType<typeof useQueryClient>, jobId: string | null | undefined) => {
  if (!jobId) return;
  queryClient.invalidateQueries({ queryKey: ['job-results', jobId] });
  queryClient.invalidateQueries({ queryKey: ['job-review-summary', jobId] });
  queryClient.invalidateQueries({ queryKey: ['job-review-result', jobId] });
  queryClient.invalidateQueries({ queryKey: ['job-proposals', jobId] });
  queryClient.invalidateQueries({ queryKey: ['job-compare', jobId] });
  queryClient.invalidateQueries({ queryKey: ['job-boundary', jobId] });
};

const invalidateWorkflowQueries = (queryClient: ReturnType<typeof useQueryClient>, workflowId: string | null | undefined) => {
  if (!workflowId) return;
  queryClient.invalidateQueries({ queryKey: ['workflow-result', workflowId] });
  queryClient.invalidateQueries({ queryKey: ['workflow-review-summary', workflowId] });
  queryClient.invalidateQueries({ queryKey: ['workflow-review-result', workflowId] });
  queryClient.invalidateQueries({ queryKey: ['workflow-review-proposals', workflowId] });
  queryClient.invalidateQueries({ queryKey: ['workflow-boundary', workflowId] });
};

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

export function useJobResults(jobId: string | null) {
  return useQuery({
    queryKey: ['job-results', jobId],
    queryFn: () => apiClient.getJobRows(jobId!),
    enabled: !!jobId,
  });
}

export function useJobReviewSummary(jobId: string | null) {
  return useQuery({
    queryKey: ['job-review-summary', jobId],
    queryFn: () => apiClient.getJobReviewSummary(jobId!),
    enabled: !!jobId,
  });
}

export function useJobReviewResult(jobId: string | null) {
  return useQuery({
    queryKey: ['job-review-result', jobId],
    queryFn: () => apiClient.getJobReviewResult(jobId!),
    enabled: !!jobId,
  });
}

export function useJobProposals(jobId: string | null) {
  return useQuery({
    queryKey: ['job-proposals', jobId],
    queryFn: () => apiClient.getJobProposals(jobId!),
    enabled: !!jobId,
  });
}

export function useJobCompare(jobId: string | null) {
  return useQuery({
    queryKey: ['job-compare', jobId],
    queryFn: () => apiClient.getJobCompare(jobId!),
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

export function useWorkflowReviewSummary(workflowId: string | null) {
  return useQuery({
    queryKey: ['workflow-review-summary', workflowId],
    queryFn: () => apiClient.getModelWorkflowReviewSummary(workflowId!).catch(() => null),
    enabled: !!workflowId,
    retry: false,
  });
}

export function useWorkflowReviewResult(workflowId: string | null) {
  return useQuery({
    queryKey: ['workflow-review-result', workflowId],
    queryFn: () => apiClient.getModelWorkflowReviewResult(workflowId!).catch(() => null),
    enabled: !!workflowId,
    retry: false,
  });
}

export function useWorkflowReviewProposals(workflowId: string | null) {
  return useQuery({
    queryKey: ['workflow-review-proposals', workflowId],
    queryFn: () => apiClient.getModelWorkflowReviewProposals(workflowId!).catch(() => ({ workflow_id: workflowId, proposals: [] })),
    enabled: !!workflowId,
    retry: false,
  });
}

export function useReviewModelWorkflow(workflowId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.reviewModelWorkflow(workflowId!),
    onSuccess: () => invalidateWorkflowQueries(queryClient, workflowId),
  });
}

export function useApplyWorkflowReviewProposal(workflowId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposalId: string) => apiClient.applyModelWorkflowReviewProposal(workflowId!, proposalId),
    onSuccess: () => invalidateWorkflowQueries(queryClient, workflowId),
  });
}

export function useDiscardWorkflowReviewProposal(workflowId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposalId: string) => apiClient.discardModelWorkflowReviewProposal(workflowId!, proposalId),
    onSuccess: () => invalidateWorkflowQueries(queryClient, workflowId),
  });
}

export function useRerunWorkflowReview(workflowId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposalIds: string[]) => apiClient.rerunModelWorkflowReview(workflowId!, proposalIds),
    onSuccess: (comparison: any) => {
      if (comparison?.after_workflow_id) {
        invalidateWorkflowQueries(queryClient, String(comparison.after_workflow_id));
      }
      invalidateWorkflowQueries(queryClient, workflowId);
    },
  });
}

export function useReviewJob(jobId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiClient.reviewJob(jobId!),
    onSuccess: () => invalidateJobQueries(queryClient, jobId),
  });
}

export function useApplyProposal(jobId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposalId: string) => apiClient.applyProposal(jobId!, proposalId),
    onSuccess: () => invalidateJobQueries(queryClient, jobId),
  });
}

export function useDiscardProposal(jobId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposalId: string) => apiClient.discardProposal(jobId!, proposalId),
    onSuccess: () => invalidateJobQueries(queryClient, jobId),
  });
}

export function useRerunProposals(jobId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proposalIds: string[]) => apiClient.rerunProposals(jobId!, proposalIds),
    onSuccess: () => invalidateJobQueries(queryClient, jobId),
  });
}
