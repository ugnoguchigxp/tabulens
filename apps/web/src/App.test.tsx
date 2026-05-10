import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';

// Mock ag-grid
vi.mock('ag-grid-react', () => ({
  AgGridReact: (props: any) => <div data-testid="ag-grid">{props.rowData?.length} rows</div>,
}));

// Mock Lucide icons to avoid noise
vi.mock('lucide-react', () => ({
  BarChart3: () => <div />,
  Settings2: () => <div />,
  Upload: () => <div />,
  Table: () => <div />,
  Plus: () => <div />,
  Trash2: () => <div />,
  Eraser: () => <div />,
  Columns: () => <div />,
  Rows: () => <div />,
  X: () => <div />,
  Wand2: () => <div />,
  Sparkles: () => <div />,
  Database: () => <div />,
  Filter: () => <div />,
  Gauge: () => <div />,
  ArrowDownNarrowWide: () => <div />,
  CheckSquare: () => <div />,
  Square: () => <div />,
  Maximize2: () => <div />,
  Play: () => <div />,
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe('App component', () => {
  it('renders correctly', () => {
    render(<App />, { wrapper: createWrapper() });
    expect(screen.getByText('TabuLens')).toBeInTheDocument();
  });
});
