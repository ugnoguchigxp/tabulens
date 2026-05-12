import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PrepareDrawer } from './prepare-drawer';

describe('PrepareDrawer', () => {
  const baseSettings = {
    run_cleansing: true,
    run_feature_selection: true,
    algorithm: 'random_forest',
    preprocessing: {
      handle_missing: 'mean',
      normalization: 'minmax',
      outlier_removal: false,
      categorical_encoding: 'label',
      calculate_importance: true,
      feature_selection_threshold: 0.01,
    },
  };

  it('calls onClose and onRun', () => {
    const onClose = vi.fn();
    const onRun = vi.fn();
    render(
      <PrepareDrawer
        settings={baseSettings}
        setSettings={vi.fn()}
        onClose={onClose}
        onRun={onRun}
        isPending={false}
        canRun
      />,
    );

    fireEvent.click(screen.getAllByRole('button')[0]);
    fireEvent.click(screen.getByRole('button', { name: /run prepare/i }));
    expect(onClose).toHaveBeenCalled();
    expect(onRun).toHaveBeenCalled();
  });

  it('toggles settings via setSettings', () => {
    const setSettings = vi.fn();
    render(
      <PrepareDrawer
        settings={baseSettings}
        setSettings={setSettings}
        onClose={vi.fn()}
        onRun={vi.fn()}
        isPending={false}
        canRun
      />,
    );

    fireEvent.click(screen.getAllByText('Enabled')[0]);
    expect(setSettings).toHaveBeenCalled();
  });
});
