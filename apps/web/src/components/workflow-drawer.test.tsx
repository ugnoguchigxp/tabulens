import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { WorkflowDrawer } from './workflow-drawer';

// Mock Lucide icons
vi.mock('lucide-react', () => ({
  Badge: () => <div />,
  Button: () => <div />,
  Card: () => <div />,
  Label: () => <div />,
  Bot: () => <div />,
  Database: () => <div />,
  Filter: () => <div />,
  Sparkles: () => <div />,
  X: () => <div />,
}));

const mockWorkbookData = {
  sheets: [
    {
      name: 'Sheet1',
      row_count: 100,
      columns: [
        { name: 'id', inferred_type: 'int' },
        { name: 'target', inferred_type: 'object' },
        { name: 'val1', inferred_type: 'float' },
      ],
    },
  ],
};

const mockMapping = {
  feature_columns: ['val1'],
  label_column: 'target',
  id_column: 'id',
};

const mockWorkflowSettings = {
  use_case: 'classification' as const,
  algorithm: 'random_forest',
  params: { task_type: 'classification', split_mode: 'ratio', train_size: 0.8, test_size: 0.2, random_state: 42 },
};

describe('WorkflowDrawer component', () => {
  it('renders correctly', () => {
    const setMapping = vi.fn();
    const setWorkflowSettings = vi.fn();
    const onClose = vi.fn();
    const onRun = vi.fn();

    render(
      <WorkflowDrawer
        workbookData={mockWorkbookData}
        selectedSheet={0}
        mapping={mockMapping}
        setMapping={setMapping}
        workflowSettings={mockWorkflowSettings}
        setWorkflowSettings={setWorkflowSettings}
        onClose={onClose}
        onRun={onRun}
        isRunning={false}
      />
    );

    expect(screen.getByText('Model Workflow')).toBeInTheDocument();
    expect(screen.getByText('Use Case')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Classification')).toBeInTheDocument();
  });

  it('calls onRun when Run Workflow button is clicked', () => {
    const onRun = vi.fn();
    render(
      <WorkflowDrawer
        workbookData={mockWorkbookData}
        selectedSheet={0}
        mapping={mockMapping}
        setMapping={vi.fn()}
        workflowSettings={mockWorkflowSettings}
        setWorkflowSettings={vi.fn()}
        onClose={vi.fn()}
        onRun={onRun}
        isRunning={false}
      />
    );

    fireEvent.click(screen.getByText('Run Workflow'));
    expect(onRun).toHaveBeenCalled();
  });

  it('updates workflow settings when use case is changed', () => {
    const setWorkflowSettings = vi.fn();
    render(
      <WorkflowDrawer
        workbookData={mockWorkbookData}
        selectedSheet={0}
        mapping={mockMapping}
        setMapping={vi.fn()}
        workflowSettings={mockWorkflowSettings}
        setWorkflowSettings={setWorkflowSettings}
        onClose={vi.fn()}
        onRun={vi.fn()}
        isRunning={false}
      />
    );

    const select = screen.getByLabelText('Use Case');
    fireEvent.change(select, { target: { value: 'prediction' } });
    
    expect(setWorkflowSettings).toHaveBeenCalled();
  });
});
