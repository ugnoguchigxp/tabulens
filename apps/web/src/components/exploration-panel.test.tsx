import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ExplorationPanel } from './exploration-panel';

describe('ExplorationPanel', () => {
  it('returns null without result', () => {
    const { container } = render(<ExplorationPanel result={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders exploration summary and evaluation', () => {
    render(
      <ExplorationPanel
        result={{
          data_profile: {
            row_count: 10,
            column_count: 3,
            missing_rate_overall: 0.1,
            columns: [{ name: 'a', warning_flags: ['id_like'] }, { name: 'b', warning_flags: [] }],
          },
          target_feasibility: {
            target_kind: 'categorical',
            feasibility: 'high',
            warnings: ['few labels'],
            baseline_metrics: { baseline_accuracy: 0.5 },
          },
          model_sweep: {
            task_type: 'classification',
            best_algorithm: 'random_forest',
            items: [
              { algorithm: 'random_forest', status: 'success', primary_metric: 0.8, gap: 0.1, warnings: [], failure_reason: null },
              { algorithm: 'svm', status: 'failed', primary_metric: null, gap: null, warnings: [], failure_reason: 'unstable' },
            ],
          },
          evaluation: {
            signal_strength: 'medium',
            model_viability: 'promising',
            overall_verdict: 'usable_signal',
            confidence: 0.7,
            reasons: ['good separation'],
            risk_flags: ['class_imbalance'],
            decision: {
              primary_message: 'Run workflow',
              recommended_path: 'run_workflow',
              primary_blocker: null,
            },
            next_actions: [
              { action: 'inspect_features', reason: 'check leakage', priority: 'high', affected_columns: ['a'] },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText('Exploration Summary')).toBeInTheDocument();
    expect(screen.getAllByText('random_forest').length).toBeGreaterThan(0);
    expect(screen.getByText('Run workflow')).toBeInTheDocument();
    expect(screen.getByText('class_imbalance')).toBeInTheDocument();
  });
});
