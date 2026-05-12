import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { ComputedChartPanel } from './computed-chart-panel';

describe('ComputedChartPanel', () => {
  it('shows fallback when no numeric columns', () => {
    render(<ComputedChartPanel rows={[{ a: 'x', b: 'y' }]} />);
    expect(screen.getByText('No numeric columns for charts.')).toBeInTheDocument();
  });

  it('renders chart source for numeric columns', () => {
    render(<ComputedChartPanel rows={[{ a: 1, b: 2 }, { a: 2, b: 3 }]} />);
    expect(screen.getByText('Chart Source')).toBeInTheDocument();
    expect(screen.getByText('a / b')).toBeInTheDocument();
  });
});
