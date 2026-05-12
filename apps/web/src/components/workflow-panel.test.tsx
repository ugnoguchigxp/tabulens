import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { WorkflowPanel } from './workflow-panel';

describe('WorkflowPanel', () => {
  it('renders metrics and rows', () => {
    render(
      <WorkflowPanel
        workflowId="wf-1"
        useCase="classification"
        result={{
          rows: [{ a: 1, b: 'x' }],
          metrics: { values: { accuracy: 0.9 } },
          metadata: { source_kind: 'prepare_job' },
        }}
      />,
    );

    expect(screen.getAllByText('classification').length).toBeGreaterThan(0);
    expect(screen.getByText('wf-1')).toBeInTheDocument();
    expect(screen.getByText('accuracy')).toBeInTheDocument();
    expect(screen.getByText('0.900')).toBeInTheDocument();
  });

  it('supports refresh action', () => {
    const onRefresh = vi.fn();
    render(
      <WorkflowPanel workflowId="wf-2" useCase="prediction" result={{ rows: [], metrics: {}, metadata: {} }} onRefresh={onRefresh} />,
    );

    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
