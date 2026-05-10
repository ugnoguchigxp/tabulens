import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { AlertTriangle, CheckCircle2, ChevronRight, RefreshCcw, Sparkles, Trash2 } from 'lucide-react';
import { BoundaryExplorer } from '@/components/boundary-explorer';

type ReviewPanelProps = {
  jobId: string;
  reviewResult: any | null;
  reviewSummary: any | null;
  proposals: any[];
  proposalStatusById: Record<string, 'applied' | 'discarded'>;
  comparison: any | null;
  boundary: any | null;
  boundaryLoading: boolean;
  boundaryError: string | null;
  boundarySuggestedLabel?: string | null;
  onUseBoundarySuggestedLabel?: () => void;
  onRefreshReview: () => void;
  onApplyProposal: (proposalId: string) => void;
  onDiscardProposal: (proposalId: string) => void;
  isRefreshing: boolean;
  isApplying: boolean;
  isDiscarding: boolean;
};

function formatRatio(value: unknown) {
  const num = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(num)) return '0';
  return num.toFixed(3);
}

export function ReviewPanel({
  jobId,
  reviewResult,
  reviewSummary,
  proposals,
  proposalStatusById,
  comparison,
  boundary,
  boundaryLoading,
  boundaryError,
  boundarySuggestedLabel,
  onUseBoundarySuggestedLabel,
  onRefreshReview,
  onApplyProposal,
  onDiscardProposal,
  isRefreshing,
  isApplying,
  isDiscarding,
}: ReviewPanelProps) {
  const assessment = reviewResult?.assessment ?? 'review_manually';
  const confidence = typeof reviewResult?.confidence === 'number' ? reviewResult.confidence : 0;
  const blockingFactors: string[] = Array.isArray(reviewResult?.blocking_factors) ? reviewResult.blocking_factors : [];
  const qualityFlags: string[] = Array.isArray(reviewSummary?.quality_flags) ? reviewSummary.quality_flags : [];

  return (
    <aside className="flex h-full w-full xl:w-[390px] shrink-0 border-t xl:border-t-0 xl:border-l bg-slate-50/40 overflow-y-auto animate-in slide-in-from-right duration-200">
      <div className="flex w-full flex-col gap-4 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Review</p>
            <h3 className="text-lg font-bold text-foreground">Analysis QA</h3>
          </div>
          <Button variant="outline" size="sm" onClick={onRefreshReview} disabled={isRefreshing || !jobId} className="gap-2">
            <RefreshCcw className={cn('size-4', isRefreshing && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        <Card className="shadow-sm">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-center justify-between gap-2">
              <Badge className="gap-1.5">
                {assessment === 'keep' ? <CheckCircle2 className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
                {String(assessment)}
              </Badge>
              <Badge variant="secondary" className="gap-1.5">
                <Sparkles className="size-3.5" />
                {confidence.toFixed(2)}
              </Badge>
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

        {reviewSummary && (
          <Card className="shadow-sm">
            <CardContent className="space-y-3 p-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Summary</p>
                <Badge variant="secondary" className="text-[10px]">{reviewSummary.algorithm}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <Metric label="Rows" value={reviewSummary.row_count} />
                <Metric label="Features" value={reviewSummary.feature_count} />
                <Metric label="Missing" value={formatRatio(reviewSummary.missing_rate)} />
                <Metric label="Islands" value={formatRatio(reviewSummary.island_rate)} />
              </div>
              <div className="flex flex-wrap gap-2">
                {qualityFlags.length > 0 ? qualityFlags.slice(0, 6).map((flag) => (
                  <Badge key={flag} variant="outline" className="text-[10px]">
                    {flag}
                  </Badge>
                )) : (
                  <Badge variant="outline" className="text-[10px]">No quality flags</Badge>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        <BoundaryExplorer
          boundary={boundary}
          isLoading={boundaryLoading}
          errorMessage={boundaryError}
          suggestedLabel={boundarySuggestedLabel}
          onUseSuggestedLabel={onUseBoundarySuggestedLabel}
        />

        <Card className="shadow-sm">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Proposals</p>
              <Badge variant="secondary" className="text-[10px]">{proposals.length}</Badge>
            </div>
            <div className="space-y-3">
              {proposals.length > 0 ? proposals.map((proposal) => {
                const proposalState = proposal.status === 'applied' || proposal.status === 'discarded'
                  ? proposal.status
                  : proposalStatusById[proposal.proposal_id] ?? 'pending'
                const isCompleted = proposalState === 'applied' || proposalState === 'discarded'
                const isManual = proposal.action === 'review_manually'
                const applyLabel = proposalState === 'applied'
                  ? 'Applied'
                  : proposalState === 'discarded'
                    ? 'Discarded'
                    : isManual
                      ? 'Note'
                      : 'Apply'

                return (
                <div
                  key={proposal.proposal_id}
                  className={cn(
                    'rounded-lg border bg-white p-3 shadow-sm transition-colors',
                    proposalState === 'applied' && 'border-emerald-200 bg-emerald-50/50',
                    proposalState === 'discarded' && 'border-slate-300 bg-slate-100/70 opacity-75',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold">{proposal.action}</p>
                      <p className="text-xs text-muted-foreground">{stringifyTarget(proposal.target)}</p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <Badge variant={proposal.safe_to_apply ? 'default' : 'outline'} className="text-[10px]">
                        {proposal.safe_to_apply ? 'safe' : 'manual'}
                      </Badge>
                      {proposalState !== 'pending' && (
                        <Badge
                          variant={proposalState === 'applied' ? 'default' : 'secondary'}
                          className="text-[10px] uppercase tracking-wide"
                        >
                          {proposalState}
                        </Badge>
                      )}
                    </div>
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
                      onClick={() => onApplyProposal(proposal.proposal_id)}
                      disabled={isApplying || isCompleted || isManual}
                    >
                      {applyLabel}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8"
                      onClick={() => onDiscardProposal(proposal.proposal_id)}
                      disabled={isDiscarding || isCompleted || isManual}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  </div>
                )
              }) : (
                <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                  No proposals yet.
                </div>
              )}
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
                <Metric label="Confidence Δ" value={formatRatio(comparison.deltas?.confidence_mean ?? 0)} />
                <Metric label="Islands Δ" value={formatRatio(comparison.deltas?.island_rate ?? 0)} />
                <Metric label="Outliers Δ" value={formatRatio(comparison.deltas?.outlier_rate ?? 0)} />
              </div>
              <div className="text-xs text-muted-foreground">
                {Array.isArray(comparison.applied_proposals) && comparison.applied_proposals.length > 0
                  ? `Applied ${comparison.applied_proposals.length} proposal(s).`
                  : 'No proposals applied yet.'}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border bg-white p-2">
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-1 text-sm font-semibold text-foreground">{String(value)}</div>
    </div>
  );
}

function stringifyTarget(target: unknown) {
  if (Array.isArray(target)) return target.join(', ');
  if (target === null || target === undefined || target === '') return 'no target';
  if (typeof target === 'object') return JSON.stringify(target);
  return String(target);
}
