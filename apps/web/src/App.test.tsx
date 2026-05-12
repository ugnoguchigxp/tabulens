import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';

const {
  mockUpdateCellInput,
  mockGetWorkbookRows,
  mockSetLocalRowData,
  mockGridEditorState,
} = vi.hoisted(() => ({
  mockUpdateCellInput: vi.fn(),
  mockGetWorkbookRows: vi.fn(async () => ({ rows: [{ feature_1: 1, feature_2: 2 }] })),
  mockSetLocalRowData: vi.fn(),
  mockGridEditorState: {
    localRowData: [{ feature_1: 1, feature_2: 2 }],
    setLocalRowData: vi.fn(),
    extraColumns: [],
    contextMenu: { visible: false, x: 0, y: 0, rowIndex: null, colId: null },
    setContextMenu: vi.fn(),
    closeContextMenu: vi.fn(),
    handleInsertRow: vi.fn(),
    handleDeleteRow: vi.fn(),
    handleInsertColumn: vi.fn(),
    handleDeleteColumn: vi.fn(),
    removeColumn: vi.fn(),
    handleClearCell: vi.fn(),
    columnKeys: ['feature_1', 'feature_2'],
    updateCellInput: vi.fn(),
    getCellRawInput: () => '=A1+B1',
    getCellAddress: () => 'A1',
    getFormulaTooltip: () => null,
  },
}));

vi.mock('ag-grid-react', () => ({
  AgGridReact: (props: any) => (
    <div data-testid="ag-grid">
      <div data-testid="grid-headers">
        {(props.columnDefs ?? []).map((col: any) => (
          <span key={col.field ?? col.headerName}>{col.headerName}</span>
        ))}
      </div>
      <button
        type="button"
        onClick={() => props.onCellFocused?.({
          rowIndex: 0,
          column: {
            getColId: () => 'feature_1',
          },
        })}
      >
        focus-cell
      </button>
    </div>
  ),
}));

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
  Search: () => <div />,
  LineChart: () => <div />,
}));

vi.mock('@/hooks/use-tabulens', () => ({
  useUploadWorkbook: () => ({
    isPending: false,
    mutate: vi.fn(),
    data: {
      workbook_id: 'wb-1',
      sheets: [
        {
          name: 'Sheet1',
          columns: [
            { name: 'feature_1', inferred_type: 'numeric', null_count: 0, unique_count: 1, sample_values: [1] },
            { name: 'feature_2', inferred_type: 'numeric', null_count: 0, unique_count: 1, sample_values: [2] },
          ],
          row_count: 1,
          preview_rows: [{ feature_1: 1, feature_2: 2 }],
        },
      ],
    },
  }),
  useRunAnalysis: () => ({ isPending: false, mutate: vi.fn() }),
  useRunModelWorkflow: () => ({ isPending: false, mutate: vi.fn() }),
  useRunExploration: () => ({ isPending: false, mutate: vi.fn() }),
  useJobResults: () => ({ data: undefined, isLoading: false }),
  useJobBoundary: () => ({ data: null, isLoading: false, error: null }),
  useWorkflowBoundary: () => ({ data: null, isLoading: false, error: null }),
}));

vi.mock('@/hooks/use-grid-editor', () => ({
  useGridEditor: () => mockGridEditorState,
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    getWorkbookRows: mockGetWorkbookRows,
  },
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
  beforeEach(() => {
    mockUpdateCellInput.mockReset();
    mockGetWorkbookRows.mockClear();
    mockSetLocalRowData.mockClear();
    mockGridEditorState.updateCellInput = mockUpdateCellInput;
    mockGridEditorState.setLocalRowData = mockSetLocalRowData;
  });

  it('shows formula bar, accepts edits, and has no recalc button', async () => {
    render(<App />, { wrapper: createWrapper() });
    await waitFor(() => expect(mockGetWorkbookRows).toHaveBeenCalled());

    expect(screen.queryByRole('button', { name: /recalc/i })).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(/type value or formula/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'focus-cell' }));
    expect(screen.getByText('A1')).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/type value or formula/i);
    fireEvent.change(input, { target: { value: '=A1*2' } });
    fireEvent.click(screen.getByRole('button', { name: /apply/i }));

    expect(mockUpdateCellInput).toHaveBeenCalledWith(0, 'feature_1', '=A1*2');
  });

  it('renders excel-style column headers', () => {
    render(<App />, { wrapper: createWrapper() });
    const headers = screen.getByTestId('grid-headers');
    expect(headers).toHaveTextContent('A (feature_1)');
    expect(headers).toHaveTextContent('B (feature_2)');
  });
});
