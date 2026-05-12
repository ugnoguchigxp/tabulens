import { getCellKey, parseA1Address, toA1Address } from './address';
import {
  cloneDependencyGraph,
  createDependencyGraph,
  removeDependencies,
  setDependencies,
} from './dependency-graph';
import { evaluateFormulaExpression } from './evaluator';
import { parseFormulaDependencies } from './parser-adapter';
import { recalcAffectedCells } from './recalc';
import type {
  FormulaCellState,
  GridRow,
  SheetState,
  WorkbookState,
} from './types';

const FORMULA_PREFIX = '=';

type CellKeyParts = {
  sheetName: string;
  rowIndex: number;
  colId: string;
};

function cloneRows(rows: GridRow[]): GridRow[] {
  return rows.map((row) => ({ ...row }));
}

function cloneCellStates(source: Map<string, FormulaCellState>): Map<string, FormulaCellState> {
  const target = new Map<string, FormulaCellState>();
  source.forEach((state, key) => {
    target.set(key, { ...state });
  });
  return target;
}

function cloneWorkbook(workbook: WorkbookState): WorkbookState {
  const sheets: Record<string, SheetState> = {};
  Object.entries(workbook.sheets).forEach(([sheetName, sheet]) => {
    sheets[sheetName] = {
      ...sheet,
      rows: cloneRows(sheet.rows),
      cellStates: cloneCellStates(sheet.cellStates),
    };
  });

  return {
    sheets,
    dependencyGraph: cloneDependencyGraph(workbook.dependencyGraph),
    volatileCells: new Set(workbook.volatileCells),
    recalcEpoch: workbook.recalcEpoch,
    workflowId: workbook.workflowId,
    predictResolver: workbook.predictResolver,
    predictCache: new Map(workbook.predictCache),
    pendingPredictRequests: new Map(workbook.pendingPredictRequests),
  };
}

function parseCellKey(cellKey: string): CellKeyParts | null {
  const tokens = cellKey.split('::');
  if (tokens.length < 3) return null;
  const [sheetName, rowIndexToken, ...colTokens] = tokens;
  const rowIndex = Number(rowIndexToken);
  const colId = colTokens.join('::');
  if (!Number.isInteger(rowIndex) || colId.length === 0) return null;
  return { sheetName, rowIndex, colId };
}

function createSheetState(name: string, rows: GridRow[]): SheetState {
  const copiedRows = cloneRows(rows);
  const columns = copiedRows.length > 0 ? Object.keys(copiedRows[0]) : [];
  return { name, columns, rows: copiedRows, cellStates: new Map<string, FormulaCellState>() };
}

function getCellState(workbook: WorkbookState, cellKey: string): FormulaCellState | null {
  const keyParts = parseCellKey(cellKey);
  if (!keyParts) return null;
  const sheet = workbook.sheets[keyParts.sheetName];
  if (!sheet) return null;
  return sheet.cellStates.get(cellKey) ?? null;
}

function setCellState(
  workbook: WorkbookState,
  sheetName: string,
  rowIndex: number,
  colId: string,
  nextState: FormulaCellState,
): void {
  const sheet = workbook.sheets[sheetName];
  if (!sheet) return;
  const row = sheet.rows[rowIndex];
  if (!row) return;
  const key = getCellKey({ sheetName, rowIndex, colId });
  row[colId] = nextState.computedValue;
  sheet.cellStates.set(key, nextState);
}

function resolveScalar(workbook: WorkbookState, sheetName: string, reference: string): unknown {
  const parsed = parseA1Address(reference);
  const sheet = workbook.sheets[sheetName];
  if (!parsed || !sheet) return 0;
  const colId = sheet.columns[parsed.columnIndex];
  if (!colId) return 0;
  const row = sheet.rows[parsed.rowIndex];
  if (!row) return 0;
  return row[colId] ?? 0;
}

function resolveRange(workbook: WorkbookState, sheetName: string, reference: string): unknown[][] {
  const [startRef, endRef] = reference.split(':');
  const start = parseA1Address(startRef);
  const end = endRef ? parseA1Address(endRef) : start;
  const sheet = workbook.sheets[sheetName];
  if (!start || !end || !sheet) return [];

  const minRow = Math.min(start.rowIndex, end.rowIndex);
  const maxRow = Math.max(start.rowIndex, end.rowIndex);
  const minCol = Math.min(start.columnIndex, end.columnIndex);
  const maxCol = Math.max(start.columnIndex, end.columnIndex);

  const matrix: unknown[][] = [];
  for (let rowIndex = minRow; rowIndex <= maxRow; rowIndex += 1) {
    const rowValues: unknown[] = [];
    for (let columnIndex = minCol; columnIndex <= maxCol; columnIndex += 1) {
      const colId = sheet.columns[columnIndex];
      if (!colId) {
        rowValues.push(null);
      } else {
        const row = sheet.rows[rowIndex];
        rowValues.push(row ? row[colId] : null);
      }
    }
    matrix.push(rowValues);
  }
  return matrix;
}

function evaluateFormula(workbook: WorkbookState, cellKey: string, now: Date): FormulaCellState | null {
  const keyParts = parseCellKey(cellKey);
  if (!keyParts) return null;
  const current = getCellState(workbook, cellKey);
  if (!current?.formula) return current;

  let pendingArgs: unknown[] | null = null;
  const result = evaluateFormulaExpression(current.formula, {
    sheetName: keyParts.sheetName,
    now,
    random: () => Math.random(),
    workflowId: workbook.workflowId,
    predictCache: workbook.predictCache,
    predictResolver: workbook.predictResolver,
    registerPendingPredict: (args) => {
      pendingArgs = args;
    },
    resolveScalar: (reference, sheetName) => resolveScalar(workbook, sheetName, reference),
    resolveRange: (reference, sheetName) => resolveRange(workbook, sheetName, reference),
  });

  if (result.value === '#PENDING' && pendingArgs) {
    workbook.pendingPredictRequests.set(cellKey, pendingArgs);
  } else {
    workbook.pendingPredictRequests.delete(cellKey);
  }

  if (result.volatile) {
    workbook.volatileCells.add(cellKey);
  } else {
    workbook.volatileCells.delete(cellKey);
  }

  return {
    ...current,
    computedValue: result.value,
    volatile: result.volatile,
  };
}

function refreshCellDependencies(workbook: WorkbookState, cellKey: string): void {
  const keyParts = parseCellKey(cellKey);
  if (!keyParts) return;

  const state = getCellState(workbook, cellKey);
  if (!state?.formula) {
    removeDependencies(workbook.dependencyGraph, cellKey);
    workbook.volatileCells.delete(cellKey);
    workbook.pendingPredictRequests.delete(cellKey);
    return;
  }

  const dependencies = parseFormulaDependencies(state.formula, keyParts.sheetName, workbook);
  setDependencies(workbook.dependencyGraph, cellKey, dependencies);
}

function initializeSheetStates(workbook: WorkbookState): void {
  Object.entries(workbook.sheets).forEach(([sheetName, sheet]) => {
    sheet.rows.forEach((row, rowIndex) => {
      sheet.columns.forEach((colId) => {
        const rawInput = row[colId];
        const formula = typeof rawInput === 'string' && rawInput.startsWith(FORMULA_PREFIX) ? rawInput : undefined;
        const key = getCellKey({ sheetName, rowIndex, colId });
        sheet.cellStates.set(key, {
          rawInput,
          formula,
          computedValue: formula ? 0 : rawInput,
          volatile: false,
        });
      });
    });
  });
}

function rebuildAllDependencies(workbook: WorkbookState): string[] {
  const changedKeys: string[] = [];
  Object.entries(workbook.sheets).forEach(([sheetName, sheet]) => {
    sheet.cellStates.forEach((state, key) => {
      if (!state.formula) {
        removeDependencies(workbook.dependencyGraph, key);
        return;
      }
      setDependencies(workbook.dependencyGraph, key, parseFormulaDependencies(state.formula, sheetName, workbook));
      changedKeys.push(key);
    });
  });
  return changedKeys;
}

function recalcFromChanges(workbook: WorkbookState, changedKeys: string[], now: Date): void {
  recalcAffectedCells(workbook.dependencyGraph, changedKeys, {
    hasFormula: (cellKey) => Boolean(getCellState(workbook, cellKey)?.formula),
    setComputedValue: (cellKey, value) => {
      const state = getCellState(workbook, cellKey);
      const keyParts = parseCellKey(cellKey);
      if (!state || !keyParts) return;
      setCellState(workbook, keyParts.sheetName, keyParts.rowIndex, keyParts.colId, {
        ...state,
        computedValue: value,
      });
    },
    evaluateFormula: (cellKey) => {
      const next = evaluateFormula(workbook, cellKey, now);
      if (!next) return '#VALUE!';
      const keyParts = parseCellKey(cellKey);
      if (!keyParts) return '#VALUE!';
      setCellState(workbook, keyParts.sheetName, keyParts.rowIndex, keyParts.colId, next);
      return next.computedValue;
    },
  });
}

export function setWorkbookPredictContext(
  workbook: WorkbookState,
  workflowId: string | null,
  predictResolver?: (featureValues: unknown[]) => unknown,
): WorkbookState {
  if (workbook.workflowId === workflowId && workbook.predictResolver === predictResolver) {
    return workbook;
  }

  const next = cloneWorkbook(workbook);
  const resolverChanged = next.predictResolver !== predictResolver || next.workflowId !== workflowId;
  next.workflowId = workflowId;
  next.predictResolver = predictResolver;
  if (resolverChanged) {
    next.predictCache.clear();
  }
  const changed: string[] = [];
  Object.values(next.sheets).forEach((sheet) => {
    sheet.cellStates.forEach((state, key) => {
      if (state.formula && /(^|[^A-Z0-9_])PREDICT\s*\(/i.test(state.formula)) {
        changed.push(key);
      }
    });
  });
  if (changed.length > 0) {
    recalcFromChanges(next, changed, new Date());
  }
  return next;
}

export function buildWorkbookState(sheetName: string, rows: GridRow[]): WorkbookState {
  return buildWorkbookStateFromSheets({ [sheetName]: rows });
}

export function buildWorkbookStateFromSheets(sheetRows: Record<string, GridRow[]>): WorkbookState {
  const sheets: Record<string, SheetState> = {};
  Object.entries(sheetRows).forEach(([name, rows]) => {
    sheets[name] = createSheetState(name, rows);
  });

  const workbook: WorkbookState = {
    sheets,
    dependencyGraph: createDependencyGraph(),
    volatileCells: new Set<string>(),
    recalcEpoch: 0,
    workflowId: null,
    predictCache: new Map<string, unknown>(),
    pendingPredictRequests: new Map<string, unknown[]>(),
  };

  initializeSheetStates(workbook);
  const changed = rebuildAllDependencies(workbook);
  recalcFromChanges(workbook, changed, new Date());
  return workbook;
}

export function updateWorkbookCell(
  workbook: WorkbookState,
  sheetName: string,
  rowIndex: number,
  colId: string,
  nextInput: unknown,
): WorkbookState {
  const nextWorkbook = cloneWorkbook(workbook);
  const sheet = nextWorkbook.sheets[sheetName];
  if (!sheet || !sheet.rows[rowIndex]) {
    return workbook;
  }

  const formula = typeof nextInput === 'string' && nextInput.startsWith(FORMULA_PREFIX) ? nextInput : undefined;
  const key = getCellKey({ sheetName, rowIndex, colId });
  setCellState(nextWorkbook, sheetName, rowIndex, colId, {
    rawInput: nextInput,
    formula,
    computedValue: formula ? 0 : nextInput,
    volatile: false,
  });
  refreshCellDependencies(nextWorkbook, key);
  recalcFromChanges(nextWorkbook, [key], new Date());
  nextWorkbook.recalcEpoch += 1;
  return nextWorkbook;
}

export function manualRecalculate(workbook: WorkbookState): WorkbookState {
  const next = cloneWorkbook(workbook);
  const changed = Array.from(next.volatileCells);
  if (changed.length === 0) {
    return next;
  }
  recalcFromChanges(next, changed, new Date());
  next.recalcEpoch += 1;
  return next;
}

export function applyPredictResult(
  workbook: WorkbookState,
  cellKey: string,
  featureValues: unknown[],
  predictedValue: unknown,
): WorkbookState {
  const next = cloneWorkbook(workbook);
  if (!next.workflowId) return next;
  const cacheKey = `${next.workflowId}::${JSON.stringify(featureValues)}`;
  next.predictCache.set(cacheKey, predictedValue);
  const keyParts = parseCellKey(cellKey);
  if (!keyParts) return next;
  recalcFromChanges(next, [cellKey], new Date());
  next.recalcEpoch += 1;
  return next;
}

export function getPendingPredictRequests(workbook: WorkbookState): Array<{ cellKey: string; featureValues: unknown[] }> {
  return Array.from(workbook.pendingPredictRequests.entries()).map(([cellKey, featureValues]) => ({ cellKey, featureValues }));
}

export function getSheetRows(workbook: WorkbookState, sheetName: string): GridRow[] {
  const sheet = workbook.sheets[sheetName];
  if (!sheet) return [];
  return cloneRows(sheet.rows);
}

export function getCellFormula(workbook: WorkbookState, sheetName: string, rowIndex: number, colId: string): string | null {
  return getCellState(workbook, getCellKey({ sheetName, rowIndex, colId }))?.formula ?? null;
}

export function getCellRawInput(
  workbook: WorkbookState,
  sheetName: string,
  rowIndex: number,
  colId: string,
): unknown {
  return getCellState(workbook, getCellKey({ sheetName, rowIndex, colId }))?.rawInput;
}

export function getCellAddressA1(workbook: WorkbookState, sheetName: string, rowIndex: number, colId: string): string | null {
  const sheet = workbook.sheets[sheetName];
  if (!sheet) return null;
  const columnIndex = sheet.columns.indexOf(colId);
  if (columnIndex < 0) return null;
  return toA1Address(rowIndex, columnIndex);
}
