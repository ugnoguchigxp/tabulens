const VALUE_ERROR = '#VALUE!';
const REF_ERROR = '#REF!';
const NA_ERROR = '#N/A';
const UNSUPPORTED_ERROR = '#UNSUPPORTED';

type Matrix = unknown[][];

function normalizeMatrix(value: unknown): Matrix | null {
  if (!Array.isArray(value)) return null;
  if (value.length === 0) return [];
  if (Array.isArray(value[0])) {
    return value as Matrix;
  }
  return [value as unknown[]];
}

function equalsLoose(a: unknown, b: unknown): boolean {
  return String(a ?? '') === String(b ?? '');
}

export function indexFn(range: unknown, rowNum: unknown, colNum?: unknown): unknown {
  const matrix = normalizeMatrix(range);
  if (!matrix) return VALUE_ERROR;
  const rowIndex = Number(rowNum) - 1;
  const colIndex = Number(colNum ?? 1) - 1;
  if (!Number.isInteger(rowIndex) || !Number.isInteger(colIndex)) return VALUE_ERROR;
  if (rowIndex < 0 || colIndex < 0) return REF_ERROR;
  const row = matrix[rowIndex];
  if (!row || colIndex >= row.length) return REF_ERROR;
  return row[colIndex];
}

export function matchFn(lookupValue: unknown, lookupArray: unknown, matchType: unknown = 0): unknown {
  const type = Number(matchType);
  if (type !== 0) return UNSUPPORTED_ERROR;
  const matrix = normalizeMatrix(lookupArray);
  if (!matrix) return VALUE_ERROR;
  const flat = matrix.flat();
  const index = flat.findIndex((item) => equalsLoose(item, lookupValue));
  return index >= 0 ? index + 1 : NA_ERROR;
}

export function vlookupFn(lookupValue: unknown, tableArray: unknown, colIndexNum: unknown, rangeLookup: unknown = false): unknown {
  if (rangeLookup) return UNSUPPORTED_ERROR;
  const matrix = normalizeMatrix(tableArray);
  if (!matrix || matrix.length === 0) return VALUE_ERROR;
  const colIndex = Number(colIndexNum) - 1;
  if (!Number.isInteger(colIndex) || colIndex < 0) return VALUE_ERROR;
  if (colIndex >= matrix[0].length) return REF_ERROR;

  const row = matrix.find((line) => equalsLoose(line[0], lookupValue));
  if (!row) return NA_ERROR;
  return row[colIndex];
}

export function xlookupFn(
  lookupValue: unknown,
  lookupArray: unknown,
  returnArray: unknown,
  ifNotFound: unknown = NA_ERROR,
  matchMode: unknown = 0,
): unknown {
  const mode = Number(matchMode);
  if (mode !== 0) return UNSUPPORTED_ERROR;

  const lookup = normalizeMatrix(lookupArray);
  const ret = normalizeMatrix(returnArray);
  if (!lookup || !ret) return VALUE_ERROR;

  const lookupFlat = lookup.flat();
  const retFlat = ret.flat();
  const index = lookupFlat.findIndex((item) => equalsLoose(item, lookupValue));
  if (index < 0) return ifNotFound;
  return retFlat[index] ?? REF_ERROR;
}
