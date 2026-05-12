import {
  dateFn,
  dateValueFn,
  dayFn,
  edateFn,
  eomonthFn,
  formatTextFn,
  monthFn,
  networkDaysFn,
  nowFn,
  todayFn,
  yearFn,
} from './functions/date';
import { indexFn, matchFn, vlookupFn, xlookupFn } from './functions/lookup';
import { predictFn, type PredictResolver } from './functions/predict';
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
} from './functions/text';
import { randBetweenFn, randFn } from './functions/volatile';

const UNSUPPORTED_ERROR = '#UNSUPPORTED';
const VALUE_ERROR = '#VALUE!';

type ResolveScalar = (reference: string, sheetName: string) => unknown;
type ResolveRange = (reference: string, sheetName: string) => unknown[][];

export interface FormulaEvaluationContext {
  sheetName: string;
  now: Date;
  random: () => number;
  workflowId: string | null;
  predictCache: Map<string, unknown>;
  predictResolver?: PredictResolver;
  registerPendingPredict?: (featureValues: unknown[]) => void;
  resolveScalar: ResolveScalar;
  resolveRange: ResolveRange;
}

export interface FormulaEvaluationResult {
  value: unknown;
  volatile: boolean;
}

function splitTopLevelArgs(input: string): string[] {
  const args: string[] = [];
  let current = '';
  let depth = 0;
  let quote: string | null = null;

  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (quote) {
      current += char;
      if (char === quote) quote = null;
      continue;
    }

    if (char === '"' || char === "'") {
      quote = char;
      current += char;
      continue;
    }

    if (char === '(') {
      depth += 1;
      current += char;
      continue;
    }

    if (char === ')') {
      depth = Math.max(0, depth - 1);
      current += char;
      continue;
    }

    if (char === ',' && depth === 0) {
      args.push(current.trim());
      current = '';
      continue;
    }

    current += char;
  }

  if (current.trim().length > 0) {
    args.push(current.trim());
  }

  return args;
}

function parseFunctionCall(expression: string): { name: string; args: string[] } | null {
  const match = expression.trim().match(/^([A-Za-z_][A-Za-z0-9_]*)\((.*)\)$/);
  if (!match) {
    return null;
  }
  return {
    name: match[1].toUpperCase(),
    args: splitTopLevelArgs(match[2]),
  };
}

function parseRefToken(token: string): { sheetName: string; ref: string } | null {
  const scoped = token.match(/^(?:'([^']+)'|([A-Za-z0-9_]+))!([A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?)$/i);
  if (scoped) {
    return {
      sheetName: (scoped[1] ?? scoped[2]).trim(),
      ref: scoped[3].toUpperCase(),
    };
  }

  const local = token.match(/^([A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?)$/i);
  if (local) {
    return {
      sheetName: '',
      ref: local[1].toUpperCase(),
    };
  }

  return null;
}

function maybeLiteral(token: string): unknown {
  const trimmed = token.trim();
  if (trimmed.length === 0) return '';
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  if (/^(TRUE|FALSE)$/i.test(trimmed)) {
    return /^TRUE$/i.test(trimmed);
  }
  const number = Number(trimmed);
  if (Number.isFinite(number)) {
    return number;
  }
  return null;
}

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function flattenValues(values: unknown[]): unknown[] {
  return values.flatMap((value) => {
    if (Array.isArray(value)) {
      return flattenValues(value as unknown[]);
    }
    return [value];
  });
}

function evalArithmetic(expression: string, context: FormulaEvaluationContext): unknown {
  const replaced = expression.replace(/(?:'([^']+)'|([A-Za-z0-9_]+))!([A-Z]+[1-9][0-9]*)|\b([A-Z]+[1-9][0-9]*)\b/g, (_match, quotedSheet, plainSheet, scopedRef, localRef) => {
    const sheetName = (quotedSheet ?? plainSheet ?? context.sheetName).trim();
    const ref = (scopedRef ?? localRef).toUpperCase();
    const value = context.resolveScalar(ref, sheetName);
    return String(toNumber(value));
  });

  if (!/^[0-9+\-*/().\s<>=!&|]+$/.test(replaced)) {
    return UNSUPPORTED_ERROR;
  }

  try {
    const fn = new Function(`return (${replaced});`);
    return fn();
  } catch {
    return VALUE_ERROR;
  }
}

function evaluateArg(token: string, context: FormulaEvaluationContext): FormulaEvaluationResult {
  const literal = maybeLiteral(token);
  if (literal !== null) {
    return { value: literal, volatile: false };
  }

  const ref = parseRefToken(token.trim());
  if (ref) {
    const sheetName = ref.sheetName || context.sheetName;
    if (ref.ref.includes(':')) {
      return {
        value: context.resolveRange(ref.ref, sheetName),
        volatile: false,
      };
    }
    return {
      value: context.resolveScalar(ref.ref, sheetName),
      volatile: false,
    };
  }

  const nested = evaluateFormulaExpression(`=${token}`, context);
  return nested;
}

export function evaluateFormulaExpression(formula: string, context: FormulaEvaluationContext): FormulaEvaluationResult {
  const expression = formula.trim().startsWith('=') ? formula.trim().slice(1) : formula.trim();
  const call = parseFunctionCall(expression);
  if (!call) {
    return { value: evalArithmetic(expression, context), volatile: false };
  }

  const evaluatedArgs = call.args.map((arg) => evaluateArg(arg, context));
  const argValues = evaluatedArgs.map((item) => item.value);
  const volatileByArg = evaluatedArgs.some((item) => item.volatile);

  const flatArgs = flattenValues(argValues as unknown[]);
  const numericArgs = flatArgs.map((value) => toNumber(value));

  switch (call.name) {
    case 'SUM':
      return { value: numericArgs.reduce((sum, value) => sum + value, 0), volatile: volatileByArg };
    case 'AVERAGE':
      return { value: numericArgs.length === 0 ? VALUE_ERROR : numericArgs.reduce((sum, value) => sum + value, 0) / numericArgs.length, volatile: volatileByArg };
    case 'MIN':
      return { value: numericArgs.length === 0 ? VALUE_ERROR : Math.min(...numericArgs), volatile: volatileByArg };
    case 'MAX':
      return { value: numericArgs.length === 0 ? VALUE_ERROR : Math.max(...numericArgs), volatile: volatileByArg };
    case 'COUNT':
      return { value: flatArgs.filter((value) => value !== null && value !== '' && value !== undefined).length, volatile: volatileByArg };
    case 'IF':
      return { value: argValues[0] ? argValues[1] : argValues[2], volatile: volatileByArg };
    case 'AND':
      return { value: flatArgs.every(Boolean), volatile: volatileByArg };
    case 'OR':
      return { value: flatArgs.some(Boolean), volatile: volatileByArg };
    case 'NOT':
      return { value: !argValues[0], volatile: volatileByArg };
    case 'ROUND':
      return { value: Number(toNumber(argValues[0]).toFixed(Number(argValues[1] ?? 0))), volatile: volatileByArg };
    case 'ABS':
      return { value: Math.abs(toNumber(argValues[0])), volatile: volatileByArg };
    case 'INDEX':
      return { value: indexFn(argValues[0], argValues[1], argValues[2]), volatile: volatileByArg };
    case 'MATCH':
      return { value: matchFn(argValues[0], argValues[1], argValues[2]), volatile: volatileByArg };
    case 'VLOOKUP':
      return { value: vlookupFn(argValues[0], argValues[1], argValues[2], argValues[3]), volatile: volatileByArg };
    case 'XLOOKUP':
      return { value: xlookupFn(argValues[0], argValues[1], argValues[2], argValues[3], argValues[4]), volatile: volatileByArg };
    case 'CONCAT':
      return { value: concatFn(...flatArgs), volatile: volatileByArg };
    case 'LEFT':
      return { value: leftFn(argValues[0], argValues[1]), volatile: volatileByArg };
    case 'RIGHT':
      return { value: rightFn(argValues[0], argValues[1]), volatile: volatileByArg };
    case 'MID':
      return { value: midFn(argValues[0], argValues[1], argValues[2]), volatile: volatileByArg };
    case 'LEN':
      return { value: lenFn(argValues[0]), volatile: volatileByArg };
    case 'TRIM':
      return { value: trimFn(argValues[0]), volatile: volatileByArg };
    case 'UPPER':
      return { value: upperFn(argValues[0]), volatile: volatileByArg };
    case 'LOWER':
      return { value: lowerFn(argValues[0]), volatile: volatileByArg };
    case 'SUBSTITUTE':
      return { value: substituteFn(argValues[0], argValues[1], argValues[2]), volatile: volatileByArg };
    case 'DATE':
      return { value: dateFn(argValues[0], argValues[1], argValues[2]), volatile: volatileByArg };
    case 'DATEVALUE':
      return { value: dateValueFn(argValues[0]), volatile: volatileByArg };
    case 'YEAR':
      return { value: yearFn(argValues[0]), volatile: volatileByArg };
    case 'MONTH':
      return { value: monthFn(argValues[0]), volatile: volatileByArg };
    case 'DAY':
      return { value: dayFn(argValues[0]), volatile: volatileByArg };
    case 'EDATE':
      return { value: edateFn(argValues[0], argValues[1]), volatile: volatileByArg };
    case 'EOMONTH':
      return { value: eomonthFn(argValues[0], argValues[1]), volatile: volatileByArg };
    case 'NETWORKDAYS':
      return { value: networkDaysFn(argValues[0], argValues[1]), volatile: volatileByArg };
    case 'TEXT':
      return { value: formatTextFn(argValues[0], argValues[1]), volatile: volatileByArg };
    case 'TODAY':
      return { value: todayFn(context.now), volatile: true };
    case 'NOW':
      return { value: nowFn(context.now), volatile: true };
    case 'RAND':
      return { value: randFn(context.random), volatile: true };
    case 'RANDBETWEEN':
      return { value: randBetweenFn(argValues[0], argValues[1], context.random), volatile: true };
    case 'PREDICT':
      {
        const value = predictFn(context.workflowId, flatArgs, context.predictCache, context.predictResolver);
        if (value === '#PENDING') {
          context.registerPendingPredict?.(flatArgs);
        }
        return { value, volatile: false };
      }
    default:
      return { value: UNSUPPORTED_ERROR, volatile: volatileByArg };
  }
}
