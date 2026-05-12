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

  it('should remove column by name', () => {
    const initialData = [{ a: 1, b: 2 }, { a: 3, b: 4 }];
    const { result } = renderHook(() => useGridEditor(initialData));

    act(() => {
      result.current.removeColumn('b');
    });

    expect(result.current.columnKeys).toEqual(['a']);
    expect(result.current.localRowData[0]).toEqual({ a: 1 });
    expect(result.current.localRowData[1]).toEqual({ a: 3 });
  });

  it('should keep raw formula while showing computed value', () => {
    const initialData = [{ a: 1, b: 2 }];
    const { result } = renderHook(() => useGridEditor(initialData, 'Sheet1'));

    act(() => {
      result.current.updateCellInput(0, 'b', '=A1+2');
    });

    expect(result.current.localRowData[0].b).toBe(3);
    expect(result.current.getFormulaTooltip(0, 'b')).toContain('=A1+2');
    expect(result.current.getCellRawInput(0, 'b')).toBe('=A1+2');
    expect(result.current.getCellAddress(0, 'b')).toBe('B1');
  });

  it('should recalculate volatile formulas manually', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-12T00:00:00Z'));
    const { result } = renderHook(() => useGridEditor([{ a: '=TODAY()' }], 'Sheet1'));
    const before = result.current.localRowData[0].a;
    vi.setSystemTime(new Date('2026-05-13T00:00:00Z'));
    act(() => {
      result.current.manualRecalculate();
    });
    const after = result.current.localRowData[0].a;
    expect(after).not.toBe(before);
    vi.useRealTimers();
  });

  it('should refresh predict formula when resolver becomes available', () => {
    type ResolverProp = {
      resolver?: (values: unknown[]) => unknown;
    };
    const { result, rerender } = renderHook(
      ({ resolver }: ResolverProp) => useGridEditor(
        [{ a: 1, b: 2, c: '=PREDICT(A1,B1)' }],
        'Sheet1',
        { workflowId: 'wf-1', predictResolver: resolver },
      ),
      { initialProps: { resolver: undefined } as ResolverProp },
    );

    expect(result.current.localRowData[0].c).toBe('#PREDICT_ERR');

    act(() => {
      rerender({
        resolver: (values: unknown[]) => `${values[0]}-${values[1]}`,
      });
    });

    expect(result.current.localRowData[0].c).toBe('1-2');
  });
});
