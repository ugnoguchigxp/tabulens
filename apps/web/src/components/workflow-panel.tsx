import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { RefreshCcw, Sparkles } from 'lucide-react';

type WorkflowPanelProps = {
  workflowId: string;
  useCase: string;
  result: any | null;
  onRefresh?: () => void;
  isRefreshing?: boolean;
};

function formatValue(value: unknown) {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') return Number.isFinite(value) ? value.toFixed(3) : '-';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (Array.isArray(value)) return `${value.length}`;
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function WorkflowPanel({
  workflowId,
  useCase,
  result,
  onRefresh,
  isRefreshing,
}: WorkflowPanelProps) {
  const metrics = result?.metrics?.values ?? result?.metrics ?? {};
  const metadata = result?.metadata ?? {};
  const rows = Array.isArray(result?.rows) ? result.rows : [];

  return (
    <aside className="flex h-full w-full xl:w-[390px] shrink-0 border-t xl:border-t-0 xl:border-l bg-slate-50/40 overflow-y-auto animate-in slide-in-from-right duration-200">
      <div className="flex w-full flex-col gap-4 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Workflow</p>
            <h3 className="text-lg font-bold text-foreground">{useCase}</h3>
          </div>
          {onRefresh && (
            <Button variant="outline" size="sm" onClick={onRefresh} disabled={isRefreshing} className="gap-2">
              <RefreshCcw className={cn('size-4', isRefreshing && 'animate-spin')} />
              Refresh
            </Button>
          )}
        </div>

        <Card className="shadow-sm">
          <CardContent className="space-y-3 p-4">
            <div className="flex items-center justify-between gap-2">
              <Badge className="gap-1.5">
                <Sparkles className="size-3.5" />
                completed
              </Badge>
              <Badge variant="secondary" className="text-[10px]">
                {rows.length} rows
              </Badge>
            </div>
            <div className="text-xs text-muted-foreground">Workflow ID</div>
            <div className="break-all text-sm font-medium">{workflowId}</div>
            {metadata?.source_kind && (
              <div className="rounded-md border bg-white p-2 text-xs">
                <span className="text-muted-foreground">Source: </span>
                <span className="font-semibold">{String(metadata.source_kind)}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="space-y-3 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Metrics</p>
            <div className="grid grid-cols-2 gap-2 text-sm">
              {Object.entries(metrics).slice(0, 8).map(([key, value]) => (
                <Metric key={key} label={key} value={value} />
              ))}
              {Object.keys(metrics).length === 0 && (
                <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground col-span-2">
                  No metrics yet.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardContent className="space-y-3 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Summary</p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between gap-2 rounded-md border bg-white p-2">
                <span className="text-muted-foreground">Use case</span>
                <span className="font-medium">{useCase}</span>
              </div>
              <div className="flex items-center justify-between gap-2 rounded-md border bg-white p-2">
                <span className="text-muted-foreground">Rows</span>
                <span className="font-medium">{rows.length}</span>
              </div>
              {Object.entries(metadata).slice(0, 4).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between gap-2 rounded-md border bg-white p-2">
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
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Result sample</p>
              <Badge variant="secondary" className="text-[10px]">{Math.min(5, rows.length)}</Badge>
            </div>
            <div className="space-y-2">
              {rows.slice(0, 5).map((row: any, index: number) => (
                <div key={index} className="rounded-lg border bg-white p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold">Row {index + 1}</span>
                    <span className="text-muted-foreground">{Object.keys(row).slice(0, 4).join(', ')}</span>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {Object.entries(row).slice(0, 4).map(([key, value]) => (
                      <div key={key} className="rounded-md bg-slate-50 p-2">
                        <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{key}</div>
                        <div className="mt-1 font-medium">{formatValue(value)}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {rows.length === 0 && (
                <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                  No result rows.
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </aside>
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
