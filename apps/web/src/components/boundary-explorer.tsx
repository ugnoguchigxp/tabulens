import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

type BoundaryAxisRange = {
  label: string;
  minimum: number;
  maximum: number;
};

type BoundaryGridCell = {
  x: number;
  y: number;
  predicted_label?: string | null;
  confidence?: number;
};

type BoundaryPoint = {
  row_id: number;
  x: number;
  y: number;
  true_label?: string | null;
  predicted_label?: string | null;
  confidence?: number;
  is_misclassified?: boolean;
  is_outlier?: boolean;
  is_island?: boolean;
  review_priority?: number;
  cluster_id?: string | null;
};

type BoundarySnapshot = {
  job_id: string;
  projection: string;
  x_axis: BoundaryAxisRange;
  y_axis: BoundaryAxisRange;
  grid_resolution: number;
  grid_step_x: number;
  grid_step_y: number;
  class_labels: string[];
  explained_variance_ratio?: number[];
  points: BoundaryPoint[];
  grid: BoundaryGridCell[];
  statistics: Record<string, any>;
};

type BoundaryExplorerProps = {
  boundary: BoundarySnapshot | null;
  isLoading: boolean;
  errorMessage?: string | null;
  suggestedLabel?: string | null;
  onUseSuggestedLabel?: (() => void) | null;
};

const PALETTE = [
  '#2563eb',
  '#db2777',
  '#f59e0b',
  '#10b981',
  '#8b5cf6',
  '#ef4444',
  '#14b8a6',
  '#0f766e',
];

export function BoundaryExplorer({
  boundary,
  isLoading,
  errorMessage,
  suggestedLabel,
  onUseSuggestedLabel,
}: BoundaryExplorerProps) {
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);

  useEffect(() => {
    setSelectedRowId(boundary?.points?.[0]?.row_id ?? null);
  }, [boundary]);

  const classColorMap = useMemo(() => {
    const map = new Map<string, string>();
    boundary?.class_labels?.forEach((label, index) => {
      map.set(label, PALETTE[index % PALETTE.length]);
    });
    return map;
  }, [boundary?.class_labels]);

  const selectedPoint = useMemo(
    () => boundary?.points?.find((point) => point.row_id === selectedRowId) ?? null,
    [boundary?.points, selectedRowId],
  );

  const pointCount = boundary?.statistics?.point_count ?? boundary?.points?.length ?? 0;
  const misclassifiedCount = boundary?.statistics?.misclassified_count ?? 0;
  const lowConfidenceCount = boundary?.statistics?.low_confidence_count ?? 0;
  const islandCount = boundary?.statistics?.island_count ?? 0;
  const outlierCount = boundary?.statistics?.outlier_count ?? 0;
  const variance = Array.isArray(boundary?.explained_variance_ratio) ? boundary.explained_variance_ratio : [];

  return (
    <Card className="shadow-sm border-sky-200/60 bg-gradient-to-br from-sky-50/70 via-white to-white">
      <CardContent className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">Boundary Explorer</p>
            <h4 className="text-sm font-bold text-foreground">Decision Surface</h4>
          </div>
          <div className="flex flex-wrap justify-end gap-1">
            <Badge variant="secondary" className="text-[10px]">PCA</Badge>
            {boundary && (
              <>
                <Badge variant="outline" className="text-[10px]">{pointCount} pts</Badge>
                <Badge variant="outline" className="text-[10px]">{boundary.grid?.length ?? 0} cells</Badge>
              </>
            )}
          </div>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            <div className="h-64 animate-pulse rounded-xl border bg-slate-100/80" />
            <div className="grid grid-cols-2 gap-2">
              <div className="h-10 animate-pulse rounded-md border bg-slate-100/80" />
              <div className="h-10 animate-pulse rounded-md border bg-slate-100/80" />
            </div>
          </div>
        ) : errorMessage ? (
          <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-sm leading-6 text-amber-900">
            <p className="font-semibold">Boundary view unavailable</p>
            <p className="mt-1">{errorMessage}</p>
            {suggestedLabel ? (
              <div className="mt-3 rounded-lg border border-amber-200 bg-white/80 p-3">
                <p className="text-xs text-amber-700">
                  このデータなら <span className="font-semibold text-amber-900">{suggestedLabel}</span> をラベルにすると分類グラフを出せます。
                </p>
                <div className="mt-2">
                  <Button
                    size="sm"
                    className="h-8"
                    onClick={onUseSuggestedLabel ?? undefined}
                    disabled={!onUseSuggestedLabel}
                  >
                    Use suggested label
                  </Button>
                </div>
              </div>
            ) : (
              <p className="mt-2 text-xs text-amber-700">
                ラベル列に `segment` のようなカテゴリ列を選び、Features から外してください。少なくとも 2 本の特徴量が必要です。
              </p>
            )}
          </div>
        ) : boundary ? (
          <>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <Metric label="Misclassified" value={misclassifiedCount} />
              <Metric label="Low confidence" value={lowConfidenceCount} />
              <Metric label="Islands" value={islandCount} />
              <Metric label="Outliers" value={outlierCount} />
            </div>

            <div className="rounded-2xl border bg-white p-3 shadow-inner">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                  {boundary.x_axis.label} / {boundary.y_axis.label}
                </div>
                <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                  {variance.length > 0 && (
                    <span>PCA variance {variance.slice(0, 2).map((value) => (value * 100).toFixed(1)).join(' / ')}%</span>
                  )}
                  <span>Click a point for details</span>
                </div>
              </div>

              <div
                className="relative aspect-square w-full overflow-hidden rounded-xl border bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.08),_transparent_30%),linear-gradient(180deg,_rgba(255,255,255,0.9),_rgba(248,250,252,0.95))]"
                style={{ maxWidth: 'min(100%, 72vh)', marginInline: 'auto' }}
              >
                <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" className="absolute inset-0 h-full w-full">
                  <defs>
                    <pattern id="boundary-grid" width="10" height="10" patternUnits="userSpaceOnUse">
                      <path d="M 10 0 L 0 0 0 10" fill="none" stroke="rgba(148,163,184,0.16)" strokeWidth="0.4" />
                    </pattern>
                  </defs>
                  <rect x="0" y="0" width="100" height="100" fill="url(#boundary-grid)" />
                  {boundary.grid.map((cell, index) => {
                    const fill = colorWithOpacity(
                      classColorMap.get(cell.predicted_label ?? '') ?? '#94a3b8',
                      0.12 + Math.max(0, Math.min(0.58, (cell.confidence ?? 0) * 0.52)),
                    );
                    const x = normalize(cell.x, boundary.x_axis.minimum, boundary.x_axis.maximum);
                    const y = 100 - normalize(cell.y, boundary.y_axis.minimum, boundary.y_axis.maximum);
                    const width = ((boundary.grid_step_x || 1) / Math.max(boundary.x_axis.maximum - boundary.x_axis.minimum, 1e-6)) * 100;
                    const height = ((boundary.grid_step_y || 1) / Math.max(boundary.y_axis.maximum - boundary.y_axis.minimum, 1e-6)) * 100;
                    return (
                      <rect
                        key={`${index}-${cell.x.toFixed(3)}-${cell.y.toFixed(3)}`}
                        x={x - width / 2}
                        y={y - height / 2}
                        width={width}
                        height={height}
                        fill={fill}
                        stroke="rgba(255,255,255,0.2)"
                        strokeWidth="0.18"
                      />
                    );
                  })}

                  {boundary.points.map((point) => {
                    const cx = normalize(point.x, boundary.x_axis.minimum, boundary.x_axis.maximum);
                    const cy = 100 - normalize(point.y, boundary.y_axis.minimum, boundary.y_axis.maximum);
                    const label = point.true_label ?? point.predicted_label ?? 'unknown';
                    const fill = classColorMap.get(label) ?? '#64748b';
                    const selected = point.row_id === selectedRowId;
                    const stroke = point.is_misclassified ? '#ef4444' : selected ? '#0f172a' : 'rgba(255,255,255,0.95)';
                    const radius = selected ? 2.7 : 1.9;
                    const opacity = point.confidence !== undefined ? 0.72 + Math.min(0.28, point.confidence * 0.25) : 0.9;
                    const dash = point.is_outlier || point.is_island ? '1.4 1.2' : undefined;

                    return (
                      <circle
                        key={point.row_id}
                        cx={cx}
                        cy={cy}
                        r={radius}
                        fill={fill}
                        fillOpacity={opacity}
                        stroke={stroke}
                        strokeWidth={selected ? 0.9 : 0.55}
                        strokeDasharray={dash}
                        style={{ cursor: 'pointer' }}
                        onClick={() => setSelectedRowId(point.row_id)}
                      >
                        <title>{buildPointTitle(point)}</title>
                      </circle>
                    );
                  })}

                  <line
                    x1="50"
                    y1="0"
                    x2="50"
                    y2="100"
                    stroke="rgba(15,23,42,0.14)"
                    strokeWidth="0.35"
                  />
                  <line
                    x1="0"
                    y1="50"
                    x2="100"
                    y2="50"
                    stroke="rgba(15,23,42,0.14)"
                    strokeWidth="0.35"
                  />
                </svg>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {boundary.class_labels.map((label) => (
                <Badge key={label} variant="outline" className="text-[10px]" style={{ borderColor: classColorMap.get(label) ?? '#cbd5e1', color: classColorMap.get(label) ?? '#334155' }}>
                  <span className="mr-1 inline-block size-2 rounded-full" style={{ backgroundColor: classColorMap.get(label) ?? '#94a3b8' }} />
                  {label}
                </Badge>
              ))}
            </div>

            <div className="rounded-xl border bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">Selected point</p>
                  <p className="text-sm font-semibold text-foreground">
                    {selectedPoint ? `Row ${selectedPoint.row_id}` : 'No point selected'}
                  </p>
                </div>
                {selectedPoint && (
                  <Badge variant={selectedPoint.is_misclassified ? 'destructive' : 'secondary'} className="text-[10px] uppercase">
                    {selectedPoint.is_misclassified ? 'mismatch' : 'match'}
                  </Badge>
                )}
              </div>

              {selectedPoint ? (
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                  <Metric label="True" value={selectedPoint.true_label ?? 'n/a'} />
                  <Metric label="Predicted" value={selectedPoint.predicted_label ?? 'n/a'} />
                  <Metric label="Confidence" value={formatRatio(selectedPoint.confidence ?? 0)} />
                  <Metric label="Priority" value={selectedPoint.review_priority ?? 0} />
                  <Metric label="Cluster" value={selectedPoint.cluster_id ?? 'n/a'} />
                  <Metric label="Flags" value={buildFlagText(selectedPoint)} />
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  境界付近の点をクリックすると、真のラベル・予測ラベル・信頼度・クラスタ情報を確認できます。
                </p>
              )}
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
            分類ジョブの結果がまだありません。
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border bg-slate-50/80 p-2">
      <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">{label}</div>
      <div className="mt-1 font-semibold text-foreground">{String(value)}</div>
    </div>
  );
}

function normalize(value: number, minimum: number, maximum: number) {
  const span = Math.max(maximum - minimum, 1e-6);
  return ((value - minimum) / span) * 100;
}

function colorWithOpacity(hex: string, opacity: number) {
  const clamped = Math.max(0.05, Math.min(1, opacity));
  if (hex.startsWith('#')) {
    const value = hex.slice(1);
    const bigint = Number.parseInt(value, 16);
    if (Number.isNaN(bigint)) return hex;
    const r = (bigint >> 16) & 255;
    const g = (bigint >> 8) & 255;
    const b = bigint & 255;
    return `rgba(${r}, ${g}, ${b}, ${clamped})`;
  }
  return hex;
}

function buildPointTitle(point: BoundaryPoint) {
  const parts = [
    `row ${point.row_id}`,
    point.true_label ? `true=${point.true_label}` : null,
    point.predicted_label ? `pred=${point.predicted_label}` : null,
    `confidence=${formatRatio(point.confidence ?? 0)}`,
  ].filter(Boolean);
  return parts.join(' | ');
}

function buildFlagText(point: BoundaryPoint) {
  const flags: string[] = [];
  if (point.is_misclassified) flags.push('mismatch');
  if (point.is_outlier) flags.push('outlier');
  if (point.is_island) flags.push('island');
  return flags.length > 0 ? flags.join(', ') : 'none';
}

function formatRatio(value: unknown) {
  const num = typeof value === 'number' ? value : Number(value);
  if (Number.isNaN(num)) return '0.000';
  return num.toFixed(3);
}
