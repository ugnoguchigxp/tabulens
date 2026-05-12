import { describe, expect, it } from 'vitest';
import { randBetweenFn, randFn } from './volatile';

describe('volatile functions', () => {
  it('returns random value', () => {
    expect(randFn(() => 0.25)).toBe(0.25);
  });

  it('supports randbetween and validation', () => {
    expect(randBetweenFn(1, 3, () => 0)).toBe(1);
    expect(randBetweenFn(1, 3, () => 0.99)).toBe(3);
    expect(randBetweenFn(3, 1, () => 0.5)).toBe('#VALUE!');
  });
});
