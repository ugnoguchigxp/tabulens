import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle2, ChevronRight, RefreshCcw, Sparkles, X } from 'lucide-react';

type ModelReviewModalProps = {
  open: boolean;
  workflowId: string;
  reviewSummary: any | null;
  reviewResult: any | null;
  proposals: any[];
  comparison: any | null;
  onClose: () => void;
  onReview: () => void;
  onDiscardProposal: (proposalId: string) => void;
  onApplyAndRerun: (proposalId: string) => void;
  isReviewing: boolean;
  isDiscarding: boolean;
  isRerunning: boolean;
};

function formatValue(value: unknown) {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') return Number.isFinite(value) ? value.toFixed(3) : '-';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `${value.length}`;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function ModelReviewModal({
  open,
  workflowId,
  reviewSummary,
  reviewResult,
  proposals,
  comparison,
  onClose,
  onReview,
  onDiscardProposal,
  onApplyAndRerun,
  isReviewing,
  isDiscarding,
  isRerunning,
}: ModelReviewModalProps) {
  if (!open) return null;

  const assessment = reviewResult?.assessment ?? 'review_manually';
  const confidence = typeof reviewResult?.confidence === 'number' ? reviewResult.confidence : 0;
  const safeToPromote = Boolean(reviewResult?.safe_to_promote);
  const blockingFactors: string[] = Array.isArray(reviewResult?.blocking_factors) ? reviewResult.blocking_factors : [];
  const recommendedActions = Array.isArray(reviewResult?.recommended_actions) ? reviewResult.recommended_actions : proposals;
  const qualityFlags: string[] = Array.isArray(reviewSummary?.quality_flags) ? reviewSummary.quality_flags : [];
  const metrics = reviewSummary?.metrics ?? {};
  const diagnostics = reviewSummary?.diagnostics ?? {};

  return (
    <div className="fixed inset-0 z-[140] flex items-center justify-center bg-slate-950/60 px-4 py-6 backdrop-blur-sm">
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between gap-3 border-b bg-slate-50 px-5 py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">Model Review</p>
            <h3 className="text-lg font-bold text-foreground">Workflow Review</h3>
            <p className="text-xs text-muted-foreground break-all">{workflowId}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={onReview} disabled={isReviewing} className="gap-2">
              <RefreshCcw className={cn('size-4', isReviewing && 'animate-spin')} />
              Review
            </Button>
            <Button variant="ghost" size="icon" className="h-9 w-9" onClick={onClose}>
              <X className="size-4" />
            </Button>
          </div>
        </div>

        <div className="grid flex-1 min-h-0 grid-cols-1 xl:grid-cols-[1.05fr_0.95fr]">
          <div className="min-h-0 overflow-y-auto border-r bg-slate-50/40 p-4">
            <div className="space-y-4">
              <Card className="shadow-sm">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <Badge className="gap-1.5">
                      {assessment === 'pass' ? <CheckCircle2 className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
                      {String(assessment)}
                    </Badge>
                    <Badge variant="secondary" className="gap-1.5">
                      <Sparkles className="size-3.5" />
                      {confidence.toFixed(2)}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={safeToPromote ? 'default' : 'outline'} className="text-[10px]">
                      {safeToPromote ? 'safe to promote' : 'manual review'}
                    </Badge>
                    {qualityFlags.slice(0, 6).map((flag) => (
                      <Badge key={flag} variant="outline" className="text-[10px]">
                        {flag}
                      </Badge>
                    ))}
                  </div>
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground">Reason</p>
                    <p className="text-sm leading-6 text-foreground">{reviewResult?.reason || 'No review result yet.'}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {blockingFactors.length > 0 ? blockingFactors.slice(0, 4).map((factor) => (
                      <Badge key={factor} variant="outline" className="bg-amber-50 text-amber-800 border-amber-200 text-[10px]">
                        {factor}
                      </Badge>
                    )) : (
                      <Badge variant="outline" className="text-[10px]">No blocking factors</Badge>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card className="shadow-sm">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Summary</p>
                    <Badge variant="secondary" className="text-[10px]">{reviewSummary?.algorithm ?? '-'}</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <Metric label="Rows" value={reviewSummary?.row_count} />
                    <Metric label="Train" value={reviewSummary?.train_count} />
                    <Metric label="Test" value={reviewSummary?.test_count} />
                    <Metric label="Unused" value={reviewSummary?.unused_count} />
                    <Metric label="Features" value={Array.isArray(reviewSummary?.feature_columns) ? reviewSummary.feature_columns.length : 0} />
                    <Metric label="Split gap" value={diagnostics?.train_test_gap ?? 0} />
                  </div>
                  <div className="space-y-2 text-xs">
                    {Object.entries(metrics).slice(0, 6).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between gap-2 rounded-md border bg-white px-2 py-1.5">
                        <span className="text-muted-foreground">{key}</span>
                        <span className="font-medium">{formatValue(value)}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="shadow-sm">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Diagnostics</p>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    {Object.entries(diagnostics).slice(0, 8).map(([key, value]) => (
                      <Metric key={key} label={key} value={value} />
                    ))}
                  </div>
                </CardContent>
              </Card>

              {comparison && (
                <Card className="shadow-sm">
                  <CardContent className="space-y-3 p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Comparison</p>
                      <Badge variant={comparison.accepted ? 'default' : 'secondary'} className="text-[10px]">
                        {comparison.accepted ? 'accepted' : 'review'}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <Metric label="Rows Δ" value={comparison.deltas?.row_count ?? 0} />
                      <Metric label="Accuracy Δ" value={comparison.deltas?.accuracy ?? 0} />
                      <Metric label="R2 Δ" value={comparison.deltas?.r2 ?? 0} />
                      <Metric label="Gap Δ" value={comparison.deltas?.train_test_gap ?? 0} />
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>

          <div className="min-h-0 overflow-y-auto p-4">
            <div className="space-y-4">
              <Card className="shadow-sm">
                <CardContent className="space-y-3 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Proposals</p>
                    <Badge variant="secondary" className="text-[10px]">{recommendedActions.length}</Badge>
                  </div>
                  <div className="space-y-3">
                    {recommendedActions.length > 0 ? recommendedActions.map((proposal: any) => (
                      <div key={proposal.proposal_id} className="rounded-lg border bg-white p-3 shadow-sm">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold">{proposal.action}</p>
                            <p className="text-xs text-muted-foreground">{stringifyTarget(proposal.target)}</p>
                          </div>
                          <Badge variant={proposal.safe_to_apply ? 'default' : 'outline'} className="text-[10px]">
                            {proposal.safe_to_apply ? 'safe' : 'manual'}
                          </Badge>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-muted-foreground">{proposal.reason || 'No reason provided.'}</p>
                        {proposal.expected_effect && (
                          <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
                            <ChevronRight className="size-3" />
                            {proposal.expected_effect}
                          </div>
                        )}
                        <div className="mt-3 flex gap-2">
                          <Button
                            size="sm"
                            className="h-8 flex-1"
                            onClick={() => {
                              onApplyAndRerun(proposal.proposal_id)
                            }}
                            disabled={isRerunning || !proposal.safe_to_apply}
                          >
                            Apply & Retrain
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8"
                            onClick={() => onDiscardProposal(proposal.proposal_id)}
                            disabled={isDiscarding}
                          >
                            Discard
                          </Button>
                        </div>
                      </div>
                    )) : (
                      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                        No active proposals.
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border bg-white p-2">
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold text-foreground">{formatValue(value)}</div>
    </div>
  );
}

function stringifyTarget(target: unknown) {
  if (target === null || target === undefined) return '-';
  if (Array.isArray(target)) return target.join(', ');
  if (typeof target === 'object') return JSON.stringify(target);
  return String(target);
}
