import { type Dispatch, type SetStateAction } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { Bot, Database, Filter, Sparkles, X } from 'lucide-react';

type ColumnLike = {
  name: string;
  inferred_type?: string;
};

type SheetLike = {
  name: string;
  row_count?: number;
  columns: ColumnLike[];
};

type WorkbookLike = {
  sheets: SheetLike[];
};

type MappingLike = {
  feature_columns: string[];
  label_column: string;
  id_column: string;
  user_id_column?: string;
  item_id_column?: string;
  rating_column?: string;
  timestamp_column?: string;
};

type WorkflowSettingsLike = {
  use_case: 'classification' | 'prediction' | 'anomaly_detection' | 'recommendation' | 'clustering' | 'noise_reduction';
  algorithm: string;
  params: Record<string, any>;
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
  recommendation: [{ value: 'popularity_baseline', label: 'Popularity Baseline' }],
  clustering: [
    { value: 'kmeans', label: 'KMeans' },
    { value: 'dbscan', label: 'DBSCAN' },
  ],
  noise_reduction: [{ value: 'isolation_forest', label: 'Isolation Forest' }],
};

function isNumericColumn(column: ColumnLike) {
  return /(int|float|double|number|numeric|decimal|real)/i.test(column.inferred_type ?? '');
}

function getUseCaseDefaults(useCase: string) {
  if (useCase === 'classification') {
    return {
      algorithm: 'random_forest',
      params: { task_type: 'classification', split_mode: 'ratio', train_size: 0.8, test_size: 0.2, random_state: 42 },
    };
  }
  if (useCase === 'prediction') {
    return {
      algorithm: 'random_forest',
      params: { task_type: 'regression', split_mode: 'ratio', train_size: 0.8, test_size: 0.2, random_state: 42 },
    };
  }
  if (useCase === 'anomaly_detection') {
    return { algorithm: 'isolation_forest', params: { contamination: 0.1 } };
  }
  if (useCase === 'recommendation') {
    return { algorithm: 'popularity_baseline', params: { top_k: 5 } };
  }
  if (useCase === 'clustering') {
    return { algorithm: 'kmeans', params: { cluster_count: 3, eps: 0.8, min_samples: 5 } };
  }
  if (useCase === 'noise_reduction') {
    return { algorithm: 'isolation_forest', params: { apply_mode: 'preview', contamination: 0.1, missing_row_threshold: 0.5 } };
  }
  return getUseCaseDefaults('classification');
}

function getCurrentColumns(workbookData: WorkbookLike | undefined, selectedSheet: number) {
  return workbookData?.sheets[selectedSheet]?.columns ?? [];
}

function updateFeatureColumns(current: string[], column: string) {
  return current.includes(column) ? current.filter((name) => name !== column) : [...current, column];
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
  const useCase = workflowSettings.use_case || 'classification';
  const splitMode = (workflowSettings.params.split_mode ?? 'ratio') as 'ratio' | 'count';
  const algorithms = USE_CASE_ALGORITHMS[useCase] ?? USE_CASE_ALGORITHMS.classification;
  const labelColumn = columns.find((column) => column.name === mapping.label_column) ?? null;
  const labelIsCategorical = labelColumn ? !isNumericColumn(labelColumn) : false;
  const rowCount = sourceRowCount ?? activeSheet?.row_count ?? 0;

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
              <p className="text-xs text-muted-foreground">Classification, prediction, anomaly, clustering, recommendation, and noise reduction</p>
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
                <Label className="text-xs">Use Case</Label>
                <select
                  value={useCase}
                  onChange={(event) => {
                    const nextUseCase = event.target.value as WorkflowSettingsLike['use_case'];
                    const defaults = getUseCaseDefaults(nextUseCase);
                    setWorkflowSettings((current) => ({
                      ...current,
                      use_case: nextUseCase,
                      algorithm: defaults.algorithm,
                      params: {
                        ...current.params,
                        ...defaults.params,
                      },
                    }));
                  }}
                  className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                >
                  <option value="classification">Classification</option>
                  <option value="prediction">Prediction / Regression</option>
                  <option value="anomaly_detection">Anomaly Detection</option>
                  <option value="recommendation">Recommendation</option>
                  <option value="clustering">Clustering</option>
                  <option value="noise_reduction">Noise Reduction</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label className="text-xs">Algorithm</Label>
                <select
                  value={workflowSettings.algorithm}
                  onChange={(event) => setWorkflowSettings((current) => ({ ...current, algorithm: event.target.value }))}
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
                <Label className="text-xs">ID Column</Label>
                <select
                  value={mapping.id_column}
                  onChange={(event) => setMapping((current) => ({ ...current, id_column: event.target.value }))}
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

              {(useCase === 'classification' || useCase === 'prediction' || useCase === 'clustering' || useCase === 'anomaly_detection' || useCase === 'noise_reduction') && (
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
                          onClick={() => {
                            setMapping((current) => ({
                              ...current,
                              feature_columns: updateFeatureColumns(current.feature_columns, column.name).filter((name) => name !== current.label_column),
                            }));
                          }}
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
                  <Label className="text-xs">Label Column</Label>
                  <select
                    value={mapping.label_column}
                    onChange={(event) => {
                      const nextLabel = event.target.value;
                      setMapping((current) => ({
                        ...current,
                        label_column: nextLabel,
                        feature_columns: current.feature_columns.filter((feature) => feature !== nextLabel),
                      }));
                    }}
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

              {useCase === 'recommendation' && (
                <div className="grid grid-cols-2 gap-3">
                  {[
                    ['user_id_column', 'User ID'],
                    ['item_id_column', 'Item ID'],
                    ['rating_column', 'Rating'],
                    ['timestamp_column', 'Timestamp'],
                  ].map(([key, label]) => (
                    <div key={key} className="space-y-2">
                      <Label className="text-xs">{label}</Label>
                      <select
                        value={(mapping as any)[key] ?? ''}
                        onChange={(event) =>
                          setMapping((current) => ({
                            ...current,
                            [key]: event.target.value,
                          }))
                        }
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
                  ))}
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
                      value={workflowSettings.params.train_size ?? 0.8}
                      step={splitMode === 'count' ? 1 : 0.05}
                      min={splitMode === 'count' ? 1 : 0.05}
                      max={splitMode === 'count' ? Math.max(2, rowCount || 2) : 0.95}
                      onChange={(value) =>
                        setWorkflowSettings((current) => ({
                          ...current,
                          params: { ...current.params, train_size: value },
                        }))
                      }
                    />
                    <NumberInput
                      label="Test Size"
                      value={workflowSettings.params.test_size ?? 0.2}
                      step={splitMode === 'count' ? 1 : 0.05}
                      min={splitMode === 'count' ? 1 : 0.05}
                      max={splitMode === 'count' ? Math.max(2, rowCount || 2) : 0.95}
                      onChange={(value) =>
                        setWorkflowSettings((current) => ({
                          ...current,
                          params: { ...current.params, test_size: value },
                        }))
                      }
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <NumberInput
                      label="Random State"
                      value={workflowSettings.params.random_state ?? 42}
                      step={1}
                      min={0}
                      onChange={(value) =>
                        setWorkflowSettings((current) => ({
                          ...current,
                          params: { ...current.params, random_state: value },
                        }))
                      }
                    />
                    <div className="space-y-2">
                      <Label className="text-xs">Split Mode</Label>
                      <select
                        value={splitMode}
                        onChange={(event) =>
                          setWorkflowSettings((current) => {
                            const nextSplitMode = event.target.value as 'ratio' | 'count';
                            const countTrain = Math.max(1, Math.floor((rowCount || 10) * 0.8));
                            const countTest = Math.max(1, (rowCount || 10) - countTrain);
                            return {
                              ...current,
                              params: {
                                ...current.params,
                                split_mode: nextSplitMode,
                                train_size: nextSplitMode === 'count' ? countTrain : 0.8,
                                test_size: nextSplitMode === 'count' ? countTest : 0.2,
                              },
                            };
                          })
                        }
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
                    value={workflowSettings.params.contamination ?? 0.1}
                    step={0.01}
                    min={0.01}
                    max={0.5}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, contamination: value },
                      }))
                    }
                  />
                  <NumberInput
                    label="k for LOF"
                    value={workflowSettings.params.n_neighbors ?? 10}
                    step={1}
                    min={2}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, n_neighbors: value },
                      }))
                    }
                  />
                </div>
              )}

              {useCase === 'recommendation' && (
                <div className="grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Top K"
                    value={workflowSettings.params.top_k ?? 5}
                    step={1}
                    min={1}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, top_k: value },
                      }))
                    }
                  />
                  <div className="space-y-2">
                    <Label className="text-xs">Baseline</Label>
                    <div className="rounded-md border bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
                      Popularity-based ranking
                    </div>
                  </div>
                </div>
              )}

              {useCase === 'clustering' && (
                <div className="grid grid-cols-3 gap-3">
                  <NumberInput
                    label="Clusters"
                    value={workflowSettings.params.cluster_count ?? 3}
                    step={1}
                    min={1}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, cluster_count: value },
                      }))
                    }
                  />
                  <NumberInput
                    label="DBSCAN eps"
                    value={workflowSettings.params.eps ?? 0.8}
                    step={0.05}
                    min={0.05}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, eps: value },
                      }))
                    }
                  />
                  <NumberInput
                    label="Min Samples"
                    value={workflowSettings.params.min_samples ?? 5}
                    step={1}
                    min={2}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, min_samples: value },
                      }))
                    }
                  />
                </div>
              )}

              {useCase === 'noise_reduction' && (
                <div className="grid grid-cols-2 gap-3">
                  <NumberInput
                    label="Missing Threshold"
                    value={workflowSettings.params.missing_row_threshold ?? 0.5}
                    step={0.05}
                    min={0.05}
                    max={0.95}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, missing_row_threshold: value },
                      }))
                    }
                  />
                  <NumberInput
                    label="Contamination"
                    value={workflowSettings.params.contamination ?? 0.1}
                    step={0.01}
                    min={0.01}
                    max={0.5}
                    onChange={(value) =>
                      setWorkflowSettings((current) => ({
                        ...current,
                        params: { ...current.params, contamination: value },
                      }))
                    }
                  />
                  <div className="space-y-2 col-span-2">
                    <Label className="text-xs">Apply Mode</Label>
                    <select
                      value={workflowSettings.params.apply_mode ?? 'preview'}
                      onChange={(event) =>
                        setWorkflowSettings((current) => ({
                          ...current,
                          params: { ...current.params, apply_mode: event.target.value },
                        }))
                      }
                      className="w-full h-9 rounded-md border bg-slate-50 px-3 text-xs"
                    >
                      <option value="preview">Preview</option>
                      <option value="auto">Auto apply</option>
                    </select>
                  </div>
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
      <Label className="text-xs">{label}</Label>
      <input
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
