import { describe, expect, it } from 'vitest';
import { buildPredictKey, predictFn } from './predict';

describe('predict function', () => {
  it('builds deterministic key', () => {
    expect(buildPredictKey('wf', [1, 'a'])).toBe('wf::[1,"a"]');
  });

  it('uses cache when present', () => {
    const cache = new Map<string, unknown>();
    cache.set('wf::[1]', 42);
    expect(predictFn('wf', [1], cache)).toBe(42);
  });

  it('returns pending without resolver and error without workflow', () => {
    const cache = new Map<string, unknown>();
    expect(predictFn('wf', [1], cache)).toBe('#PENDING');
    expect(predictFn(null, [1], cache)).toBe('#PREDICT_ERR');
  });

  it('resolves and caches using resolver', () => {
    const cache = new Map<string, unknown>();
    expect(predictFn('wf', [1, 2], cache, (values) => values.join('-'))).toBe('1-2');
    expect(predictFn('wf', [1, 2], cache, () => 'x')).toBe('1-2');
  });
});
