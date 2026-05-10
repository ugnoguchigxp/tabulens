import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Sparkles, AlertTriangle } from 'lucide-react'

type ExplorationResult = {
  data_profile: {
    row_count: number
    column_count: number
    missing_rate_overall: number
    columns: Array<{
      name: string
      warning_flags: string[]
    }>
  }
  target_feasibility: {
    target_kind: string
    feasibility: string
    warnings: string[]
    baseline_metrics: Record<string, number>
  }
  model_sweep: {
    task_type: string
    best_algorithm: string | null
    items: Array<{
      algorithm: string
      status: string
      primary_metric: number | null
      gap: number | null
      warnings: string[]
      failure_reason: string | null
    }>
  }
  evaluation?: {
    signal_strength: 'none' | 'weak' | 'medium' | 'strong' | 'unknown'
    model_viability: 'not_useful' | 'unclear' | 'promising' | 'strong' | 'unknown'
    overall_verdict: 'try_more' | 'usable_signal' | 'needs_better_features' | 'needs_better_target' | 'not_enough_data'
    confidence: number
    reasons: string[]
    risk_flags: string[]
    next_actions: Array<{
      action: string
      reason: string
      priority: 'high' | 'medium' | 'low'
    }>
  }
}

type Props = {
  result: ExplorationResult | null
}

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

export function ExplorationPanel({ result }: Props) {
  if (!result) return null

  const riskyColumns = result.data_profile.columns.filter((c) => c.warning_flags.length > 0)
  const successfulModels = result.model_sweep.items.filter((i) => i.status === 'success')
  const evaluation = result.evaluation

  return (
    <aside className="w-[360px] shrink-0 border-l bg-slate-50/40 overflow-y-auto">
      <div className="p-4 space-y-4">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold flex items-center gap-2"><Sparkles className="size-4" /> Exploration Summary</h3>
          <p className="text-[11px] text-muted-foreground">Quick signal check for feature quality and model viability.</p>
        </div>

        <Card>
          <CardContent className="p-3 space-y-2 text-xs">
            <div className="flex justify-between"><span>Rows</span><span className="font-mono">{result.data_profile.row_count}</span></div>
            <div className="flex justify-between"><span>Columns</span><span className="font-mono">{result.data_profile.column_count}</span></div>
            <div className="flex justify-between"><span>Missing (overall)</span><span className="font-mono">{pct(result.data_profile.missing_rate_overall)}</span></div>
            <div className="flex justify-between"><span>Risky columns</span><span className="font-mono">{riskyColumns.length}</span></div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-3 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span>Target kind</span>
              <Badge variant="outline">{result.target_feasibility.target_kind}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>Feasibility</span>
              <Badge variant="secondary">{result.target_feasibility.feasibility}</Badge>
            </div>
            {Object.entries(result.target_feasibility.baseline_metrics).map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span>{k}</span>
                <span className="font-mono">{Number(v).toFixed(4)}</span>
              </div>
            ))}
            {result.target_feasibility.warnings.length > 0 && (
              <div className="pt-1 space-y-1">
                {result.target_feasibility.warnings.map((warning) => (
                  <div key={warning} className="inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-800 mr-1">
                    <AlertTriangle className="size-3" />
                    {warning}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-3 space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span>Quick Sweep</span>
              <Badge>{result.model_sweep.task_type}</Badge>
            </div>
            <div className="text-[11px]">
              Best: <span className="font-semibold">{result.model_sweep.best_algorithm ?? 'n/a'}</span>
            </div>
            {successfulModels.map((item) => (
              <div key={item.algorithm} className="rounded border bg-white px-2 py-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{item.algorithm}</span>
                  <span className="font-mono">{item.primary_metric == null ? '-' : item.primary_metric.toFixed(4)}</span>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  gap: {item.gap == null ? '-' : item.gap.toFixed(4)}
                </div>
              </div>
            ))}
            {result.model_sweep.items.filter((i) => i.status === 'failed').map((item) => (
              <div key={item.algorithm} className="rounded border border-red-200 bg-red-50 px-2 py-1.5 text-[10px] text-red-700">
                {item.algorithm}: {item.failure_reason ?? 'failed'}
              </div>
            ))}
          </CardContent>
        </Card>

        {evaluation && (
          <Card>
            <CardContent className="p-3 space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span>Evaluation</span>
                <Badge variant="outline">{evaluation.overall_verdict}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded border bg-white px-2 py-1">
                  <p className="text-[10px] text-muted-foreground">Signal</p>
                  <p className="font-semibold">{evaluation.signal_strength}</p>
                </div>
                <div className="rounded border bg-white px-2 py-1">
                  <p className="text-[10px] text-muted-foreground">Viability</p>
                  <p className="font-semibold">{evaluation.model_viability}</p>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span>Confidence</span>
                <span className="font-mono">{pct(evaluation.confidence)}</span>
              </div>

              {evaluation.reasons.length > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Reasons</p>
                  <div className="space-y-1">
                    {evaluation.reasons.map((reason, index) => (
                      <p key={`${reason}-${index}`} className="rounded border bg-white px-2 py-1 text-[10px]">
                        {reason}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {evaluation.risk_flags.length > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Risk Flags</p>
                  <div>
                    {evaluation.risk_flags.map((flag) => (
                      <span key={flag} className="mr-1 inline-flex items-center gap-1 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-800">
                        <AlertTriangle className="size-3" />
                        {flag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {evaluation.next_actions.length > 0 && (
                <div className="space-y-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Next Actions</p>
                  <div className="space-y-1">
                    {evaluation.next_actions.map((action) => (
                      <div key={action.action} className="rounded border bg-white px-2 py-1 text-[10px]">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold">{action.action}</span>
                          <Badge variant="secondary" className="h-4 px-1 text-[9px]">
                            {action.priority}
                          </Badge>
                        </div>
                        <p className="mt-1 text-muted-foreground">{action.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </aside>
  )
}
