import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useWorkflowSettings } from './use-workflow-settings';
import type { WorkflowSettingsLike, MappingLike } from './use-workflow-settings';

describe('useWorkflowSettings hook', () => {
  const initialMapping: MappingLike = {
    feature_columns: [],
    label_column: '',
    id_column: '',
  };

  const initialSettings: WorkflowSettingsLike = {
    use_case: 'classification',
    algorithm: 'random_forest',
    params: { train_size: 0.8 },
  };

  it('handles use case change and sets defaults', () => {
    const setMapping = vi.fn();
    const setWorkflowSettings = vi.fn();
    
    const { result } = renderHook(() => 
      useWorkflowSettings(initialMapping, setMapping, initialSettings, setWorkflowSettings, 100)
    );

    act(() => {
      result.current.handleUseCaseChange('anomaly_detection');
    });

    expect(setWorkflowSettings).toHaveBeenCalledWith(expect.any(Function));
    
    // Simulate the state update to verify the result of the function passed to setWorkflowSettings
    const updateFn = setWorkflowSettings.mock.calls[0][0];
    const nextState = updateFn(initialSettings);
    expect(nextState.use_case).toBe('anomaly_detection');
    expect(nextState.algorithm).toBe('isolation_forest');
    expect(nextState.params.contamination).toBe(0.1);
  });

  it('toggles feature columns and ensures they are not the label', () => {
    const setMapping = vi.fn();
    const setWorkflowSettings = vi.fn();
    const mappingWithLabel = { ...initialMapping, label_column: 'target' };
    
    const { result } = renderHook(() => 
      useWorkflowSettings(mappingWithLabel, setMapping, initialSettings, setWorkflowSettings, 100)
    );

    act(() => {
      result.current.toggleFeatureColumn('feature1');
    });

    const updateFn = setMapping.mock.calls[0][0];
    const nextMapping = updateFn(mappingWithLabel);
    expect(nextMapping.feature_columns).toContain('feature1');

    // Toggle off
    act(() => {
      result.current.toggleFeatureColumn('feature1');
    });
    const updateFnOff = setMapping.mock.calls[1][0];
    const nextMappingOff = updateFnOff({ ...mappingWithLabel, feature_columns: ['feature1'] });
    expect(nextMappingOff.feature_columns).not.toContain('feature1');
  });

  it('prevents label column from being a feature', () => {
    const setMapping = vi.fn();
    const { result } = renderHook(() => 
      useWorkflowSettings(initialMapping, setMapping, initialSettings, vi.fn(), 100)
    );

    act(() => {
      result.current.handleLabelColumnChange('new_label');
    });

    const updateFn = setMapping.mock.calls[0][0];
    const nextMapping = updateFn({ ...initialMapping, feature_columns: ['new_label', 'other'] });
    expect(nextMapping.label_column).toBe('new_label');
    expect(nextMapping.feature_columns).not.toContain('new_label');
    expect(nextMapping.feature_columns).toContain('other');
  });
});
