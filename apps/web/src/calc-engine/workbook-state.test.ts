import { describe, expect, it, vi } from 'vitest';
import {
  applyPredictResult,
  buildWorkbookState,
  buildWorkbookStateFromSheets,
  getCellAddressA1,
  getCellFormula,
  getPendingPredictRequests,
  getSheetRows,
  manualRecalculate,
  setWorkbookPredictContext,
  updateWorkbookCell,
} from './workbook-state';

describe('workbook-state', () => {
  it('evaluates formula and preserves raw input', () => {
    const workbook = buildWorkbookState('Sheet1', [{ a: 1, b: '=1+2' }]);

    expect(getSheetRows(workbook, 'Sheet1')[0].b).toBe(3);
    expect(getCellFormula(workbook, 'Sheet1', 0, 'b')).toBe('=1+2');
  });

  it('resolves A1 references on update', () => {
    const workbook = buildWorkbookState('Sheet1', [{ a: 4, b: 0 }]);
    const updated = updateWorkbookCell(workbook, 'Sheet1', 0, 'b', '=A1+3');

    expect(getSheetRows(updated, 'Sheet1')[0].b).toBe(7);
    expect(getCellAddressA1(updated, 'Sheet1', 0, 'b')).toBe('B1');
  });

  it('recalculates dependent chain from changed cell', () => {
    const workbook = buildWorkbookState('Sheet1', [{ a: 1, b: '=A1+1', c: '=B1+1' }]);
    const updated = updateWorkbookCell(workbook, 'Sheet1', 0, 'a', 3);

    expect(getSheetRows(updated, 'Sheet1')[0].b).toBe(4);
    expect(getSheetRows(updated, 'Sheet1')[0].c).toBe(5);
  });

  it('marks cyclic references as #CIRC!', () => {
    const workbook = buildWorkbookState('Sheet1', [{ a: '=B1', b: '=A1' }]);

    expect(getSheetRows(workbook, 'Sheet1')[0].a).toBe('#CIRC!');
    expect(getSheetRows(workbook, 'Sheet1')[0].b).toBe('#CIRC!');
  });

  it('recalculates cross-sheet dependencies', () => {
    const workbook = buildWorkbookStateFromSheets({
      Sheet1: [{ a: 1, b: 0 }],
      Sheet2: [{ a: 0, b: '=Sheet1!A1+1' }],
    });

    const updated = updateWorkbookCell(workbook, 'Sheet1', 0, 'a', 10);
    expect(getSheetRows(updated, 'Sheet2')[0].b).toBe(11);
  });

  it('marks cross-sheet cyclic references as #CIRC!', () => {
    const workbook = buildWorkbookStateFromSheets({
      Sheet1: [{ a: '=Sheet2!B1', b: 0 }],
      Sheet2: [{ a: 0, b: '=Sheet1!A1' }],
    });

    expect(getSheetRows(workbook, 'Sheet1')[0].a).toBe('#CIRC!');
    expect(getSheetRows(workbook, 'Sheet2')[0].b).toBe('#CIRC!');
  });

  it('evaluates lookup/text/date functions', () => {
    const workbook = buildWorkbookState('Sheet1', [{
      a: 1,
      b: 2,
      c: '=VLOOKUP(1,A1:B1,2,FALSE)',
      d: '=CONCAT("x", "y")',
      e: '=YEAR(DATE(2026,5,12))',
    }]);
    const row = getSheetRows(workbook, 'Sheet1')[0];
    expect(row.c).toBe(2);
    expect(row.d).toBe('xy');
    expect(row.e).toBe(2026);
  });

  it('re-evaluates volatile formulas on manual recalc', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-05-12T00:00:00Z'));
    const workbook = buildWorkbookState('Sheet1', [{ a: '=TODAY()', b: '=NOW()' }]);
    const before = getSheetRows(workbook, 'Sheet1')[0];
    vi.setSystemTime(new Date('2026-05-13T00:00:00Z'));
    const recalculated = manualRecalculate(workbook);
    const after = getSheetRows(recalculated, 'Sheet1')[0];
    expect(after.a).not.toBe(before.a);
    expect(after.b).not.toBe(before.b);
    vi.useRealTimers();
  });

  it('handles predict cache and pending flow', () => {
    const workbook = setWorkbookPredictContext(
      buildWorkbookState('Sheet1', [{ a: 10, b: 20, c: '=PREDICT(A1,B1)' }]),
      'wf-1',
    );
    const pending = getPendingPredictRequests(workbook);
    expect(pending).toHaveLength(1);
    const resolved = applyPredictResult(workbook, pending[0].cellKey, pending[0].featureValues, 'YES');
    expect(getSheetRows(resolved, 'Sheet1')[0].c).toBe('YES');
  });
});
