import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ReviewPanel } from './review-panel';

// Mock UI components
vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled }: any) => (
    <button onClick={onClick} disabled={disabled}>{children}</button>
  ),
}));
vi.mock('@/components/ui/badge', () => ({
  Badge: ({ children }: any) => <div>{children}</div>,
}));
vi.mock('@/components/ui/card', () => ({
  Card: ({ children }: any) => <div>{children}</div>,
  CardContent: ({ children }: any) => <div>{children}</div>,
}));

// Mock BoundaryExplorer since it's tested separately
vi.mock('@/components/boundary-explorer', () => ({
  BoundaryExplorer: () => <div data-testid="boundary-explorer" />,
}));

const mockReviewResult = {
  assessment: 'keep',
  confidence: 0.95,
  reason: 'Data is clean',
  blocking_factors: [],
};

const mockReviewSummary = {
  algorithm: 'random_forest',
  row_count: 100,
  feature_count: 10,
  missing_rate: 0.01,
  island_rate: 0.05,
  quality_flags: ['consistent'],
};

const mockProposals = [
  {
    proposal_id: 'p1',
    action: 'Drop column',
    target: 'col1',
    safe_to_apply: true,
    reason: 'High missing rate',
    status: 'pending',
  },
];

describe('ReviewPanel component', () => {
  it('renders correctly with review data', () => {
    render(
      <ReviewPanel
        jobId="job-123"
        reviewResult={mockReviewResult}
        reviewSummary={mockReviewSummary}
        proposals={mockProposals}
        proposalStatusById={{}}
        comparison={null}
        boundary={null}
        boundaryLoading={false}
        boundaryError={null}
        onRefreshReview={vi.fn()}
        onApplyProposal={vi.fn()}
        onDiscardProposal={vi.fn()}
        isRefreshing={false}
        isApplying={false}
        isDiscarding={false}
      />
    );

    expect(screen.getByText('Prepare QA')).toBeInTheDocument();
    expect(screen.getByText('keep')).toBeInTheDocument();
    expect(screen.getByText('Data is clean')).toBeInTheDocument();
    expect(screen.getByText('Drop column')).toBeInTheDocument();
  });

  it('calls onApplyProposal when Apply is clicked', () => {
    const onApplyProposal = vi.fn();
    render(
      <ReviewPanel
        jobId="job-123"
        reviewResult={mockReviewResult}
        reviewSummary={mockReviewSummary}
        proposals={mockProposals}
        proposalStatusById={{}}
        comparison={null}
        boundary={null}
        boundaryLoading={false}
        boundaryError={null}
        onRefreshReview={vi.fn()}
        onApplyProposal={onApplyProposal}
        onDiscardProposal={vi.fn()}
        isRefreshing={false}
        isApplying={false}
        isDiscarding={false}
      />
    );

    fireEvent.click(screen.getByText('Apply'));
    expect(onApplyProposal).toHaveBeenCalledWith('p1');
  });
});
