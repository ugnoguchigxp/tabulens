import { type Dispatch, type SetStateAction, useCallback } from 'react';

export type ColumnLike = {
  name: string;
  inferred_type?: string;
};

export type MappingLike = {
  feature_columns: string[];
  label_column: string;
  id_column: string;
  user_id_column?: string;
  item_id_column?: string;
  rating_column?: string;
  timestamp_column?: string;
};

export type WorkflowSettingsLike = {
  use_case: 'classification' | 'prediction' | 'anomaly_detection' | 'clustering';
  algorithm: string;
  params: Record<string, unknown>;
};

export function getUseCaseDefaults(useCase: string) {
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
  if (useCase === 'clustering') {
    return { algorithm: 'kmeans', params: { cluster_count: 3, eps: 0.8, min_samples: 5 } };
  }
  return getUseCaseDefaults('classification');
}

export function useWorkflowSettings(
  _mapping: MappingLike,
  setMapping: Dispatch<SetStateAction<MappingLike>>,
  _workflowSettings: WorkflowSettingsLike,
  setWorkflowSettings: Dispatch<SetStateAction<WorkflowSettingsLike>>,
  rowCount: number
) {
  const handleUseCaseChange = useCallback((nextUseCase: WorkflowSettingsLike['use_case']) => {
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
  }, [setWorkflowSettings]);

  const handleAlgorithmChange = useCallback((algorithm: string) => {
    setWorkflowSettings((current) => ({ ...current, algorithm }));
  }, [setWorkflowSettings]);

  const handleParamChange = useCallback((key: string, value: unknown) => {
    setWorkflowSettings((current) => ({
      ...current,
      params: { ...current.params, [key]: value },
    }));
  }, [setWorkflowSettings]);

  const handleSplitModeChange = useCallback((nextSplitMode: 'ratio' | 'count') => {
    const countTrain = Math.max(1, Math.floor((rowCount || 10) * 0.8));
    const countTest = Math.max(1, (rowCount || 10) - countTrain);
    setWorkflowSettings((current) => ({
      ...current,
      params: {
        ...current.params,
        split_mode: nextSplitMode,
        train_size: nextSplitMode === 'count' ? countTrain : 0.8,
        test_size: nextSplitMode === 'count' ? countTest : 0.2,
      },
    }));
  }, [setWorkflowSettings, rowCount]);

  const handleIdColumnChange = useCallback((idColumn: string) => {
    setMapping((current) => ({ ...current, id_column: idColumn }));
  }, [setMapping]);

  const handleLabelColumnChange = useCallback((nextLabel: string) => {
    setMapping((current) => ({
      ...current,
      label_column: nextLabel,
      feature_columns: current.feature_columns.filter((feature) => feature !== nextLabel),
    }));
  }, [setMapping]);

  const toggleFeatureColumn = useCallback((columnName: string) => {
    setMapping((current) => {
      const isSelected = current.feature_columns.includes(columnName);
      const nextFeatures = isSelected
        ? current.feature_columns.filter((name) => name !== columnName)
        : [...current.feature_columns, columnName];
      
      return {
        ...current,
        feature_columns: nextFeatures.filter((name) => name !== current.label_column),
      };
    });
  }, [setMapping]);

  const handleMappingKeyChange = useCallback((key: string, value: string) => {
    setMapping((current) => ({
      ...current,
      [key]: value,
    }));
  }, [setMapping]);

  return {
    handleUseCaseChange,
    handleAlgorithmChange,
    handleParamChange,
    handleSplitModeChange,
    handleIdColumnChange,
    handleLabelColumnChange,
    toggleFeatureColumn,
    handleMappingKeyChange,
  };
}
