import { useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

type GridRow = Record<string, unknown>;

interface ComputedChartPanelProps {
  rows: GridRow[];
}

function numericColumns(rows: GridRow[]): string[] {
  if (rows.length === 0) return [];
  return Object.keys(rows[0]).filter((key) => rows.some((row) => typeof row[key] === 'number' && Number.isFinite(row[key] as number)));
}

function toChartData(rows: GridRow[], xKey: string, yKey: string) {
  return rows
    .map((row, index) => ({
      row: index + 1,
      x: Number(row[xKey]),
      y: Number(row[yKey]),
    }))
    .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y));
}

export function ComputedChartPanel({ rows }: ComputedChartPanelProps) {
  const columns = useMemo(() => numericColumns(rows), [rows]);
  const xKey = columns[0] ?? null;
  const yKey = columns[1] ?? columns[0] ?? null;
  const data = useMemo(() => {
    if (!xKey || !yKey) return [];
    return toChartData(rows, xKey, yKey);
  }, [rows, xKey, yKey]);

  if (!xKey || !yKey || data.length === 0) {
    return (
      <Card className="shadow-sm">
        <CardContent className="p-4 text-sm text-muted-foreground">No numeric columns for charts.</CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant="secondary">Chart Source</Badge>
        <span className="text-xs text-muted-foreground">{xKey} / {yKey}</span>
      </div>

      <Card className="shadow-sm">
        <CardContent className="p-3">
          <div className="h-48 w-full">
            <ResponsiveContainer>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="row" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="y" stroke="#0f766e" dot={false} name={yKey} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardContent className="p-3">
          <div className="h-48 w-full">
            <ResponsiveContainer>
              <BarChart data={data}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="row" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="y" fill="#2563eb" name={yKey} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="shadow-sm">
        <CardContent className="p-3">
          <div className="h-48 w-full">
            <ResponsiveContainer>
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="x" name={xKey} />
                <YAxis dataKey="y" name={yKey} />
                <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                <Scatter data={data} fill="#7c3aed" name={`${xKey} vs ${yKey}`} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
