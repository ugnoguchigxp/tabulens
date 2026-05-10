import { useState, useCallback, useMemo } from 'react';

type GridRow = Record<string, unknown>;

interface ContextMenuState {
  x: number;
  y: number;
  visible: boolean;
  rowIndex: number | null;
  colId: string | null;
}

export function useGridEditor(initialData: GridRow[]) {
  const [localRowData, setLocalRowData] = useState<GridRow[]>(initialData);
  const [extraColumns, setExtraColumns] = useState<string[]>([]);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    x: 0,
    y: 0,
    visible: false,
    rowIndex: null,
    colId: null,
  });

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
  }, [contextMenu.rowIndex, localRowData, closeContextMenu]);

  const handleDeleteRow = useCallback(() => {
    if (contextMenu.rowIndex === null) return;
    setLocalRowData((prev) => {
      const newData = [...prev];
      newData.splice(contextMenu.rowIndex as number, 1);
      return newData;
    });
    closeContextMenu();
  }, [contextMenu.rowIndex, closeContextMenu]);

  const handleInsertColumn = useCallback(() => {
    const colName = prompt('Enter column name:');
    if (colName) {
      setExtraColumns((prev) => [...prev, colName]);
      setLocalRowData((prev) => prev.map((row) => ({ ...row, [colName]: null })));
    }
    closeContextMenu();
  }, [closeContextMenu]);

  const removeColumn = useCallback((colId: string) => {
    if (!colId) return;
    setLocalRowData((prev) => prev.map((row) => {
      const nr = { ...row };
      delete nr[colId];
      return nr;
    }));
    setExtraColumns((prev) => prev.filter((c) => c !== colId));
  }, []);

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
  }, [contextMenu, closeContextMenu]);

  const columnKeys = useMemo(() => {
    if (localRowData.length > 0) {
      return Object.keys(localRowData[0]);
    }
    return [];
  }, [localRowData]);

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
  };
}
