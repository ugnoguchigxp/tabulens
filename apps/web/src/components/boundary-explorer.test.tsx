import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { BoundaryExplorer } from './boundary-explorer';

// Mock UI components
vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
}));
vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children, className }: any) => <div className={className}>{children}</div>,
}));
vi.mock('@/components/ui/card', () => ({
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
}));

const mockBoundary = {
  job_id: 'job-123',
  projection: 'pca',
  x_axis: { label: 'PC1', minimum: -1, maximum: 1 },
  y_axis: { label: 'PC2', minimum: -1, maximum: 1 },
  grid_resolution: 10,
  grid_step_x: 0.1,
  grid_step_y: 0.1,
  class_labels: ['A', 'B'],
  points: [
    { row_id: 1, x: 0, y: 0, true_label: 'A', predicted_label: 'A', confidence: 0.9 },
    { row_id: 2, x: 0.5, y: 0.5, true_label: 'A', predicted_label: 'B', confidence: 0.4, is_misclassified: true },
  ],
  grid: [
    { x: 0, y: 0, predicted_label: 'A', confidence: 0.8 },
  ],
  statistics: { point_count: 2, misclassified_count: 1 },
};

describe('BoundaryExplorer component', () => {
  it('renders correctly with boundary data', () => {
    render(
      <BoundaryExplorer
        boundary={mockBoundary as any}
        isLoading={false}
      />
    );

    expect(screen.getByText('Decision Surface')).toBeInTheDocument();
    expect(screen.getByText('2 pts')).toBeInTheDocument();
    expect(screen.getByText('PC1 / PC2')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    render(<BoundaryExplorer boundary={null} isLoading={true} />);
    expect(screen.getByText('Decision Surface')).toBeInTheDocument();
    expect(screen.queryByText('pts')).toBeNull();
  });

  it('renders error message and suggested label', () => {
    const onUseSuggestedLabel = vi.fn();
    render(
      <BoundaryExplorer
        boundary={null}
        isLoading={false}
        errorMessage="Too few features"
        suggestedLabel="target_col"
        onUseSuggestedLabel={onUseSuggestedLabel}
      />
    );

    expect(screen.getByText('Boundary view unavailable')).toBeInTheDocument();
    expect(screen.getByText('target_col')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Use suggested label'));
    expect(onUseSuggestedLabel).toHaveBeenCalled();
  });
});
