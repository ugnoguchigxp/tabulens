import { describe, expect, it } from 'vitest';
import { indexFn, matchFn, vlookupFn, xlookupFn } from './lookup';

describe('lookup functions', () => {
  it('supports INDEX', () => {
    expect(indexFn([[1, 2], [3, 4]], 2, 2)).toBe(4);
    expect(indexFn([[1, 2]], 2, 1)).toBe('#REF!');
  });

  it('supports MATCH exact only', () => {
    expect(matchFn('b', ['a', 'b', 'c'], 0)).toBe(2);
    expect(matchFn('x', ['a', 'b'], 0)).toBe('#N/A');
    expect(matchFn('b', ['a', 'b'], 1)).toBe('#UNSUPPORTED');
  });

  it('supports VLOOKUP exact and errors', () => {
    const table = [['k1', 10], ['k2', 20]];
    expect(vlookupFn('k2', table, 2, false)).toBe(20);
    expect(vlookupFn('k2', table, 3, false)).toBe('#REF!');
    expect(vlookupFn('k2', table, 2, true)).toBe('#UNSUPPORTED');
    expect(vlookupFn('k9', table, 2, false)).toBe('#N/A');
  });

  it('supports XLOOKUP exact and if_not_found', () => {
    expect(xlookupFn('b', ['a', 'b'], [10, 20], 'NA', 0)).toBe(20);
    expect(xlookupFn('x', ['a', 'b'], [10, 20], 'NA', 0)).toBe('NA');
    expect(xlookupFn('b', ['a', 'b'], [10, 20], 'NA', 1)).toBe('#UNSUPPORTED');
  });
});
