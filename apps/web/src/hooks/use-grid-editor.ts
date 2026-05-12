import { useState, useCallback, useEffect, useMemo } from 'react';
import {
  applyPredictResult,
  buildWorkbookState,
  getCellAddressA1,
  getCellFormula,
  getCellRawInput as getWorkbookCellRawInput,
  getPendingPredictRequests,
  getSheetRows,
  manualRecalculate as manualRecalculateWorkbook,
  setWorkbookPredictContext,
  updateWorkbookCell,
} from '@/calc-engine/workbook-state';
import type { GridRow, WorkbookState } from '@/calc-engine/types';

interface ContextMenuState {
  x: number;
  y: number;
  visible: boolean;
  rowIndex: number | null;
  colId: string | null;
}

type GridRowStateUpdater = GridRow[] | ((prev: GridRow[]) => GridRow[]);

interface GridEditorOptions {
  workflowId?: string | null;
  predictResolver?: (featureValues: unknown[]) => unknown;
}

export function useGridEditor(initialData: GridRow[], activeSheetName = 'Sheet1', options: GridEditorOptions = {}) {
  const workflowId = options.workflowId ?? null;
  const predictResolver = options.predictResolver;
  const [localRowDataState, setLocalRowDataState] = useState<GridRow[]>(() => {
    const workbook = setWorkbookPredictContext(
      buildWorkbookState(activeSheetName, initialData),
      workflowId,
      predictResolver,
    );
    return getSheetRows(workbook, activeSheetName);
  });
  const [workbookState, setWorkbookState] = useState<WorkbookState>(() => (
    setWorkbookPredictContext(
      buildWorkbookState(activeSheetName, initialData),
      workflowId,
      predictResolver,
    )
  ));
  const [extraColumns, setExtraColumns] = useState<string[]>([]);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    x: 0,
    y: 0,
    visible: false,
    rowIndex: null,
    colId: null,
  });
  const localRowData = localRowDataState;

  const resolvePendingPredicts = useCallback((workbook: WorkbookState): WorkbookState => {
    let nextWorkbook = workbook;
    const pending = getPendingPredictRequests(nextWorkbook);
    pending.forEach(({ cellKey, featureValues }) => {
      if (workflowId == null || !predictResolver) {
        nextWorkbook = applyPredictResult(nextWorkbook, cellKey, featureValues, '#PREDICT_ERR');
        return;
      }
      const predicted = predictResolver(featureValues);
      nextWorkbook = applyPredictResult(nextWorkbook, cellKey, featureValues, predicted);
    });
    return nextWorkbook;
  }, [workflowId, predictResolver]);

  const setLocalRowData = useCallback((nextState: GridRowStateUpdater) => {
    setLocalRowDataState((prev) => {
      const nextRows = typeof nextState === 'function'
        ? nextState(prev)
        : nextState;
      const workbook = setWorkbookPredictContext(
        buildWorkbookState(activeSheetName, nextRows),
        workflowId,
        predictResolver,
      );
      setWorkbookState(workbook);
      return getSheetRows(workbook, activeSheetName);
    });
  }, [activeSheetName, workflowId, predictResolver]);

  const closeContextMenu = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
  }, []);

  const handleInsertRow = useCallback((offset: number) => {
    if (contextMenu.rowIndex === null) return;
    const newRow: GridRow = {};
    Object.keys(localRowData[0] ?? {}).forEach((k) => {
      newRow[k] = null;
    });
    setLocalRowData((prev) => {
      const newData = [...prev];
      newData.splice((contextMenu.rowIndex as number) + offset, 0, newRow);
      return newData;
    });
    closeContextMenu();
  }, [contextMenu.rowIndex, localRowData, closeContextMenu, setLocalRowData]);

  const handleDeleteRow = useCallback(() => {
    if (contextMenu.rowIndex === null) return;
    setLocalRowData((prev) => {
      const newData = [...prev];
      newData.splice(contextMenu.rowIndex as number, 1);
      return newData;
    });
    closeContextMenu();
  }, [contextMenu.rowIndex, closeContextMenu, setLocalRowData]);

  const handleInsertColumn = useCallback(() => {
    const colName = prompt('Enter column name:');
    if (colName) {
      setExtraColumns((prev) => [...prev, colName]);
      setLocalRowData((prev) => prev.map((row) => ({ ...row, [colName]: null })));
    }
    closeContextMenu();
  }, [closeContextMenu, setLocalRowData]);

  const removeColumn = useCallback((colId: string) => {
    if (!colId) return;
    setLocalRowData((prev) => prev.map((row) => {
      const nr = { ...row };
      delete nr[colId];
      return nr;
    }));
    setExtraColumns((prev) => prev.filter((c) => c !== colId));
  }, [setLocalRowData]);

  const handleDeleteColumn = useCallback(() => {
    if (!contextMenu.colId) return;
    removeColumn(contextMenu.colId);
    closeContextMenu();
  }, [contextMenu.colId, closeContextMenu, removeColumn]);

  const handleClearCell = useCallback(() => {
    if (contextMenu.rowIndex !== null && contextMenu.colId) {
      const { rowIndex, colId } = contextMenu;
      setLocalRowData((prev) => {
        const nd = [...prev];
        nd[rowIndex][colId] = null;
        return nd;
      });
    }
    closeContextMenu();
  }, [contextMenu, closeContextMenu, setLocalRowData]);

  const columnKeys = useMemo(() => {
    if (localRowData.length > 0) {
      return Object.keys(localRowData[0]);
    }
    return [];
  }, [localRowData]);

  const updateCellInput = useCallback((rowIndex: number, colId: string, value: unknown) => {
    setWorkbookState((prev) => {
      const workbookWithContext = setWorkbookPredictContext(prev, workflowId, predictResolver);
      let nextWorkbook = updateWorkbookCell(workbookWithContext, activeSheetName, rowIndex, colId, value);
      nextWorkbook = resolvePendingPredicts(nextWorkbook);
      setLocalRowDataState(getSheetRows(nextWorkbook, activeSheetName));
      return nextWorkbook;
    });
  }, [activeSheetName, workflowId, predictResolver, resolvePendingPredicts]);

  const manualRecalculate = useCallback(() => {
    setWorkbookState((prev) => {
      const workbookWithContext = setWorkbookPredictContext(prev, workflowId, predictResolver);
      let nextWorkbook = manualRecalculateWorkbook(workbookWithContext);
      nextWorkbook = resolvePendingPredicts(nextWorkbook);
      setLocalRowDataState(getSheetRows(nextWorkbook, activeSheetName));
      return nextWorkbook;
    });
  }, [activeSheetName, workflowId, predictResolver, resolvePendingPredicts]);

  useEffect(() => {
    setWorkbookState((prev) => {
      const workbookWithContext = setWorkbookPredictContext(prev, workflowId, predictResolver);
      const nextWorkbook = resolvePendingPredicts(workbookWithContext);
      setLocalRowDataState(getSheetRows(nextWorkbook, activeSheetName));
      return nextWorkbook;
    });
  }, [workflowId, predictResolver, activeSheetName, resolvePendingPredicts]);

  const getFormulaTooltip = useCallback((rowIndex: number, colId: string): string | null => {
    const formula = getCellFormula(workbookState, activeSheetName, rowIndex, colId);
    if (!formula) {
      return null;
    }
    const address = getCellAddressA1(workbookState, activeSheetName, rowIndex, colId);
    if (!address) {
      return formula;
    }
    return `${address}: ${formula}`;
  }, [workbookState, activeSheetName]);

  const getCellRawInput = useCallback((rowIndex: number, colId: string): unknown => (
    getWorkbookCellRawInput(workbookState, activeSheetName, rowIndex, colId)
  ), [workbookState, activeSheetName]);

  const getCellAddress = useCallback((rowIndex: number, colId: string): string | null => (
    getCellAddressA1(workbookState, activeSheetName, rowIndex, colId)
  ), [workbookState, activeSheetName]);

  return {
    localRowData,
    setLocalRowData,
    extraColumns,
    contextMenu,
    setContextMenu,
    closeContextMenu,
    handleInsertRow,
    handleDeleteRow,
    handleInsertColumn,
    handleDeleteColumn,
    removeColumn,
    handleClearCell,
    columnKeys,
    updateCellInput,
    manualRecalculate,
    getCellRawInput,
    getCellAddress,
    getFormulaTooltip,
  };
}
