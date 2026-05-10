import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { useGridEditor } from './use-grid-editor';

describe('useGridEditor hook', () => {
  it('should initialize with data', () => {
    const initialData = [{ a: 1, b: 2 }];
    const { result } = renderHook(() => useGridEditor(initialData));
    expect(result.current.localRowData).toEqual(initialData);
    expect(result.current.columnKeys).toEqual(['a', 'b']);
  });

  it('should handle row insertion', () => {
    const initialData = [{ a: 1 }];
    const { result } = renderHook(() => useGridEditor(initialData));
    
    act(() => {
      result.current.setContextMenu({ x: 0, y: 0, visible: true, rowIndex: 0, colId: 'a' });
    });
    
    act(() => {
      result.current.handleInsertRow(1);
    });
    
    expect(result.current.localRowData).toHaveLength(2);
    expect(result.current.localRowData[1]).toEqual({ a: null });
  });

  it('should handle column insertion', () => {
    vi.stubGlobal('prompt', vi.fn().mockReturnValue('new_col'));
    const initialData = [{ a: 1 }];
    const { result } = renderHook(() => useGridEditor(initialData));
    
    act(() => {
      result.current.handleInsertColumn();
    });
    
    expect(result.current.extraColumns).toContain('new_col');
    expect(result.current.localRowData[0]).toHaveProperty('new_col');
  });
});
