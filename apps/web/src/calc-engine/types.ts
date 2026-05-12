export type GridRow = Record<string, unknown>;

export interface CellAddress {
  sheetName: string;
  rowIndex: number;
  colId: string;
  columnIndex: number;
  a1: string;
}

export interface FormulaCellState {
  rawInput: unknown;
  formula?: string;
  computedValue: unknown;
  volatile?: boolean;
}

export interface SheetState {
  name: string;
  columns: string[];
  rows: GridRow[];
  cellStates: Map<string, FormulaCellState>;
}

export interface DependencyGraphState {
  dependsOn: Map<string, Set<string>>;
  dependents: Map<string, Set<string>>;
}

export interface WorkbookState {
  sheets: Record<string, SheetState>;
  dependencyGraph: DependencyGraphState;
  volatileCells: Set<string>;
  recalcEpoch: number;
  workflowId: string | null;
  predictResolver?: (featureValues: unknown[]) => unknown;
  predictCache: Map<string, unknown>;
  pendingPredictRequests: Map<string, unknown[]>;
}
