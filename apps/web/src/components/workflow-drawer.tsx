import { type Dispatch, type SetStateAction } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { Bot, Database, Filter, Sparkles, X } from 'lucide-react';
import { useWorkflowSettings, type ColumnLike, type MappingLike, type WorkflowSettingsLike } from '@/hooks/use-workflow-settings';

type WorkbookLike = {
  sheets: {
    name: string;
    row_count?: number;
    columns: ColumnLike[];
  }[];
};

type WorkflowDrawerProps = {
  workbookData: WorkbookLike | undefined;
  selectedSheet: number;
  sourceColumns?: ColumnLike[];
  sourceRowCount?: number;
  sourceLabel?: string;
  mapping: MappingLike;
  setMapping: Dispatch<SetStateAction<MappingLike>>;
  workflowSettings: WorkflowSettingsLike;
  setWorkflowSettings: Dispatch<SetStateAction<WorkflowSettingsLike>>;
  onClose: () => void;
  onRun: () => void;
  isRunning: boolean;
};

const USE_CASE_ALGORITHMS: Record<string, Array<{ value: string; label: string }>> = {
  classification: [
    { value: 'random_forest', label: 'Random Forest' },
    { value: 'gradient_boosting', label: 'Gradient Boosting' },
    { value: 'svm', label: 'SVM' },
    { value: 'logistic_regression', label: 'Logistic Regression' },
  ],
  prediction: [
    { value: 'random_forest', label: 'Random Forest' },
    { value: 'gradient_boosting', label: 'Gradient Boosting' },
    { value: 'svm', label: 'SVM' },
    { value: 'linear_regression', label: 'Linear Regression' },
  ],
  anomaly_detection: [
    { value: 'isolation_forest', label: 'Isolation Forest' },
    { value: 'one_class_svm', label: 'One-Class SVM' },
    { value: 'local_outlier_factor', label: 'Local Outlier Factor' },
  ],
  clustering: [
    { value: 'kmeans', label: 'KMeans' },
    { value: 'dbscan', label: 'DBSCAN' },
  ],
};

function isNumericColumn(column: ColumnLike) {
  return /(int|float|double|number|numeric|decimal|real)/i.test(column.inferred_type ?? '');
}

function getCurrentColumns(workbookData: WorkbookLike | undefined, selectedSheet: number) {
  return workbookData?.sheets[selectedSheet]?.columns ?? [];
}

export function WorkflowDrawer({
  workbookData,
  selectedSheet,
  sourceColumns,
  sourceRowCount,
  sourceLabel,
  mapping,
  setMapping,
  workflowSettings,
  setWorkflowSettings,
  onClose,
  onRun,
  isRunning,
}: WorkflowDrawerProps) {
  const activeSheet = workbookData?.sheets[selectedSheet];
  const columns = sourceColumns?.length ? sourceColumns : getCurrentColumns(workbookData, selectedSheet);
  const rowCount = sourceRowCount ?? activeSheet?.row_count ?? 0;

  const {
    handleUseCaseChange,
    handleAlgorithmChange,
    handleParamChange,
    handleSplitModeChange,
    handleIdColumnChange,
    handleLabelColumnChange,
    toggleFeatureColumn,
  } = useWorkflowSettings(mapping, setMapping, workflowSettings, setWorkflowSettings, rowCount);

  const useCase = workflowSettings.use_case || 'classification';
  const splitMode = (workflowSettings.params.split_mode ?? 'ratio') as 'ratio' | 'count';
  const algorithms = USE_CASE_ALGORITHMS[useCase] ?? USE_CASE_ALGORITHMS.classification;
  const labelColumn = columns.find((column) => column.name === mapping.label_column) ?? null;
  const labelIsCategorical = labelColumn ? !isNumericColumn(labelColumn) : false;

  return (
    <div className="fixed inset-0 z-[120] flex justify-end bg-background/45 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-[460px] bg-background border-l shadow-2xl h-full flex flex-col animate-in slide-in-from-right duration-300">
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-3">
            <div className="bg-primary/10 p-2 rounded-full">
              <Database className="size-6 text-primary" />
            </div>
            <div>
              <h2 className="text-xl font-bold">Model Workflow</h2>
              <p className="text-xs text-muted-foreground">Classification, prediction, anomaly detection, and clustering</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="size-5" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <Card className="border-slate-200 shadow-sm">
            <CardContent className="space-y-4 p-4">
              <div className="space-y-2">
                <Label htmlFor="use-case-select" className="text-xs">Use Case</Label>
                <select
                  id="use-case-select"
                  value={useCase}
                  onChange={(event) => handleUseCaseChange(event.target.value as any)}
                  className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                >
                  <option value="classification">Classification</option>
                  <option value="prediction">Prediction / Regression</option>
                  <option value="anomaly_detection">Anomaly Detection</option>
                  <option value="clustering">Clustering</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="algorithm-select" className="text-xs">Algorithm</Label>
                <select
                  id="algorithm-select"
                  value={workflowSettings.algorithm}
                  onChange={(event) => handleAlgorithmChange(event.target.value)}
                  className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                >
                  {algorithms.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardContent className="space-y-4 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Mapping</p>
                  <p className="text-[10px] text-muted-foreground">Choose the columns that match the selected use case.</p>
                </div>
                <Badge variant="outline" className="text-[10px]">
                  {sourceLabel ?? activeSheet?.name ?? 'Sheet'}
                </Badge>
              </div>

              <div className="space-y-2">
                <Label htmlFor="id-column-select" className="text-xs">ID Column</Label>
                <select
                  id="id-column-select"
                  value={mapping.id_column}
                  onChange={(event) => handleIdColumnChange(event.target.value)}
                  className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                >
                  <option value="">None</option>
                  {columns.map((column) => (
                    <option key={column.name} value={column.name}>
                      {column.name}
                    </option>
                  ))}
                </select>
              </div>

              {(useCase === 'classification' || useCase === 'prediction' || useCase === 'clustering' || useCase === 'anomaly_detection') && (
                <div className="space-y-2">
                  <Label className="text-xs">Feature Columns</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {columns.map((column) => {
                      const isLabel = mapping.label_column === column.name;
                      const isSelected = mapping.feature_columns.includes(column.name);
                      return (
                        <button
                          key={column.name}
                          disabled={isLabel}
                          onClick={() => toggleFeatureColumn(column.name)}
                          className={cn(
                            'inline-flex items-center rounded-md border px-2 py-1 text-[10px] font-medium transition-all',
                            isLabel && 'cursor-not-allowed border-amber-300 bg-amber-50 text-amber-800',
                            !isLabel && isSelected
                              ? 'bg-primary text-primary-foreground border-primary shadow-sm'
                              : !isLabel && 'bg-background border-slate-200 hover:border-primary/30',
                          )}
                        >
                          {column.name}
                          {isNumericColumn(column) && <span className="ml-1 text-[8px] uppercase tracking-wide opacity-70">num</span>}
                        </button>
                      );
                    })}
                  </div>
                  <p className="text-[10px] text-muted-foreground">The current label, ID, and special columns are excluded automatically.</p>
                </div>
              )}

              {(useCase === 'classification' || useCase === 'prediction') && (
                <div className="space-y-2">
                  <Label htmlFor="label-column-select" className="text-xs">Label Column</Label>
                  <select
                    id="label-column-select"
                    value={mapping.label_column}
                    onChange={(event) => handleLabelColumnChange(event.target.value)}
                    className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                  >
                    <option value="">None</option>
                    {columns.map((column) => (
                      <option key={column.name} value={column.name}>
                        {column.name}
                      </option>
                    ))}
                  </select>
                  <p className="text-[10px] text-muted-foreground">
                    {labelColumn
                      ? useCase === 'classification'
                        ? labelIsCategorical
                          ? 'A categorical label is selected for classification.'
                          : `The selected label (${labelColumn.name}) is numeric. Classification usually needs a categorical label.`
                        : 'A target column is selected for regression prediction.'
                      : useCase === 'classification'
                        ? 'Pick the class label column you want to classify.'
                        : 'Pick the numeric target column you want to predict.'}
                  </p>
                </div>
              )}

            </CardContent>
          </Card>

          <Card className="border-emerald-200 bg-emerald-50/60 shadow-sm">
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-emerald-800">
                <Filter className="size-4" />
                Prepared Input
              </div>
              <p className="text-xs leading-5 text-emerald-900">
                Workflow は Prepare 済みデータだけを入力にします。クレンジング、欠損処理、外れ値処理、特徴量選択は Prepare 側で確定してください。
                学習時は検証データへの leakage を避けるため、モデル内部の fit / transform pipeline だけを保存します。
              </p>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardContent className="space-y-4 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                <Sparkles className="size-4" />
                Workflow Options
              </div>

              {(useCase === 'classification' || useCase === 'prediction') && (
                <>
                  {useCase === 'classification' ? (
                    <div className="rounded-md border bg-blue-50 px-3 py-2 text-xs text-blue-900">
                      Classification trains a supervised classifier and outputs predicted class, confidence, correctness, and holdout metrics.
                    </div>
                  ) : (
                    <div className="rounded-md border bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
                      Prediction / Regression trains a supervised regression model and outputs predicted value, residual, and holdout metrics.
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <NumberInput
                      label="Train Size"
                      value={Number(workflowSettings.params.train_size ?? 0.8)}
                      step={splitMode === 'count' ? 1 : 0.05}
                      min={splitMode === 'count' ? 1 : 0.05}
                      max={splitMode === 'count' ? Math.max(2, rowCount || 2) : 0.95}
                      onChange={(value) => handleParamChange('train_size', value)}
                    />
                    <NumberInput
                      label="Test Size"
                      value={Number(workflowSettings.params.test_size ?? 0.2)}
                      step={splitMode === 'count' ? 1 : 0.05}
                      min={splitMode === 'count' ? 1 : 0.05}
                      max={splitMode === 'count' ? Math.max(2, rowCount || 2) : 0.95}
                      onChange={(value) => handleParamChange('test_size', value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <NumberInput
                      label="Random State"
                      value={Number(workflowSettings.params.random_state ?? 42)}
                      step={1}
                      min={0}
                      onChange={(value) => handleParamChange('random_state', value)}
                    />
                    <div className="space-y-2">
                      <Label htmlFor="split-mode-select" className="text-xs">Split Mode</Label>
                      <select
                        id="split-mode-select"
                        value={splitMode}
                        onChange={(event) => handleSplitModeChange(event.target.value as any)}
                        className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                      >
                        <option value="ratio">Ratio</option>
                        <option value="count">Count</option>
                      </select>
                    </div>
                  </div>
                </>
              )}

              {useCase === 'anomaly_detection' && (
                <div className="grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Contamination"
                    value={Number(workflowSettings.params.contamination ?? 0.1)}
                    step={0.01}
                    min={0.01}
                    max={0.5}
                    onChange={(value) => handleParamChange('contamination', value)}
                  />
                  <NumberInput
                    label="k for LOF"
                    value={Number(workflowSettings.params.n_neighbors ?? 10)}
                    step={1}
                    min={2}
                    onChange={(value) => handleParamChange('n_neighbors', value)}
                  />
                </div>
              )}

              {useCase === 'clustering' && (
                <div className="grid grid-cols-3 gap-3">
                  <NumberInput
                    label="Clusters"
                    value={Number(workflowSettings.params.cluster_count ?? 3)}
                    step={1}
                    min={1}
                    onChange={(value) => handleParamChange('cluster_count', value)}
                  />
                  <NumberInput
                    label="DBSCAN eps"
                    value={Number(workflowSettings.params.eps ?? 0.8)}
                    step={0.05}
                    min={0.05}
                    onChange={(value) => handleParamChange('eps', value)}
                  />
                  <NumberInput
                    label="Min Samples"
                    value={Number(workflowSettings.params.min_samples ?? 5)}
                    step={1}
                    min={2}
                    onChange={(value) => handleParamChange('min_samples', value)}
                  />
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="border-t bg-slate-50 p-4">
          <div className="flex items-center gap-3">
            <Button className="flex-1 gap-2" onClick={onRun} disabled={isRunning || !activeSheet}>
              <Bot className="size-4" />
              Run Workflow
            </Button>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NumberInput({
  label,
  value,
  step,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  step: number;
  min?: number;
  max?: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={`number-input-${label.replace(/\s+/g, '-').toLowerCase()}`} className="text-xs">{label}</Label>
      <input
        id={`number-input-${label.replace(/\s+/g, '-').toLowerCase()}`}
        type="number"
        value={Number.isFinite(value) ? value : 0}
        step={step}
        min={min}
        max={max}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
      />
    </div>
  );
}
