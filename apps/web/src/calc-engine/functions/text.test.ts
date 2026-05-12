import { describe, expect, it } from 'vitest';
import {
  concatFn,
  leftFn,
  lenFn,
  lowerFn,
  midFn,
  rightFn,
  substituteFn,
  trimFn,
  upperFn,
} from './text';

describe('text functions', () => {
  it('handles concat and length', () => {
    expect(concatFn('a', 1, null, 'b')).toBe('a1b');
    expect(lenFn('hello')).toBe(5);
  });

  it('handles left/right/mid', () => {
    expect(leftFn('hello', 2)).toBe('he');
    expect(rightFn('hello', 2)).toBe('lo');
    expect(midFn('hello', 2, 3)).toBe('ell');
  });

  it('returns errors for invalid slicing args', () => {
    expect(leftFn('hello', -1)).toBe('#VALUE!');
    expect(rightFn('hello', -1)).toBe('#VALUE!');
    expect(midFn('hello', 0, 2)).toBe('#VALUE!');
  });

  it('normalizes spaces and casing', () => {
    expect(trimFn('  a   b  ')).toBe('a b');
    expect(upperFn('ab')).toBe('AB');
    expect(lowerFn('AB')).toBe('ab');
  });

  it('substitutes text', () => {
    expect(substituteFn('a-b-c', '-', '/')).toBe('a/b/c');
  });
});
