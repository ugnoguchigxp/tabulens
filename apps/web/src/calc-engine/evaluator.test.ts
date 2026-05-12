import { describe, expect, it } from 'vitest';
import { evaluateFormulaExpression } from './evaluator';

const baseContext = {
  sheetName: 'Sheet1',
  now: new Date('2026-05-12T00:00:00Z'),
  random: () => 0.5,
  workflowId: 'wf-1',
  predictCache: new Map<string, unknown>(),
  resolveScalar: () => 0,
  resolveRange: () => [],
};

describe('evaluator', () => {
  it('supports lookup functions', () => {
    const result = evaluateFormulaExpression('=XLOOKUP(2,{1,2,3},{"A","B","C"})', {
      ...baseContext,
      resolveRange: () => [[1, 2, 3]],
    });
    expect(result.value).toBe('#UNSUPPORTED');
  });

  it('supports text and date functions', () => {
    const text = evaluateFormulaExpression('=LEFT("HELLO",2)', baseContext);
    const date = evaluateFormulaExpression('=YEAR(DATE(2026,5,12))', baseContext);
    expect(text.value).toBe('HE');
    expect(date.value).toBe(2026);
  });

  it('marks volatile formulas', () => {
    const nowValue = evaluateFormulaExpression('=NOW()', baseContext);
    const randValue = evaluateFormulaExpression('=RANDBETWEEN(1,10)', baseContext);
    expect(nowValue.volatile).toBe(true);
    expect(randValue.volatile).toBe(true);
  });

  it('returns unsupported for unknown functions', () => {
    const result = evaluateFormulaExpression('=UNKNOWN(1)', baseContext);
    expect(result.value).toBe('#UNSUPPORTED');
  });

  it('uses predict cache', () => {
    const cache = new Map<string, unknown>();
    const first = evaluateFormulaExpression('=PREDICT(1,2)', {
      ...baseContext,
      predictCache: cache,
      predictResolver: (values) => values.join('-'),
    });
    const second = evaluateFormulaExpression('=PREDICT(1,2)', {
      ...baseContext,
      predictCache: cache,
      predictResolver: () => 'x',
    });
    expect(first.value).toBe('1-2');
    expect(second.value).toBe('1-2');
  });
});
