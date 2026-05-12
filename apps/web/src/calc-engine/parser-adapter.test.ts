import { describe, expect, it } from 'vitest';
import { parseFormulaDependencies } from './parser-adapter';
import { buildWorkbookStateFromSheets } from './workbook-state';

describe('parser-adapter', () => {
  it('extracts same-sheet and cross-sheet dependencies', () => {
    const workbook = buildWorkbookStateFromSheets({
      Sheet1: [{ a: 1, b: 2 }],
      Sheet2: [{ a: 3, b: 4 }],
    });

    const deps = parseFormulaDependencies('=A1+Sheet2!B1', 'Sheet1', workbook);
    expect(Array.from(deps)).toContain('Sheet1::0::a');
    expect(Array.from(deps)).toContain('Sheet2::0::b');
  });

  it('extracts range dependencies', () => {
    const workbook = buildWorkbookStateFromSheets({
      Sheet1: [{ a: 1, b: 2, c: 3 }],
    });

    const deps = parseFormulaDependencies('=SUM(A1:C1)', 'Sheet1', workbook);
    expect(deps.size).toBe(3);
  });
});
