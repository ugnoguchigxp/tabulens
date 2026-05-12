import { getCellKey, parseA1Address } from './address';
import type { WorkbookState } from './types';

const CELL_TOKEN_PATTERN = /(?:'([^']+)'|([A-Za-z0-9_]+))!([A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?)|\b([A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?)\b/g;

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return 0;
}

function getSheet(workbook: WorkbookState, sheetName: string) {
  return workbook.sheets[sheetName];
}

function expandReferenceToken(
  workbook: WorkbookState,
  sheetName: string,
  token: string,
): string[] {
  const [startToken, endToken] = token.split(':');
  const start = parseA1Address(startToken);
  const end = endToken ? parseA1Address(endToken) : start;

  if (!start || !end) {
    return [];
  }

  const sheet = getSheet(workbook, sheetName);
  if (!sheet) {
    return [];
  }

  const minRow = Math.min(start.rowIndex, end.rowIndex);
  const maxRow = Math.max(start.rowIndex, end.rowIndex);
  const minCol = Math.min(start.columnIndex, end.columnIndex);
  const maxCol = Math.max(start.columnIndex, end.columnIndex);

  const keys: string[] = [];
  for (let rowIndex = minRow; rowIndex <= maxRow; rowIndex += 1) {
    for (let columnIndex = minCol; columnIndex <= maxCol; columnIndex += 1) {
      const colId = sheet.columns[columnIndex];
      if (!colId) {
        continue;
      }
      keys.push(getCellKey({
        sheetName,
        rowIndex,
        colId,
      }));
    }
  }

  return keys;
}

export function parseFormulaDependencies(
  formula: string,
  currentSheetName: string,
  workbook: WorkbookState,
): Set<string> {
  const dependencies = new Set<string>();
  const expression = formula.startsWith('=') ? formula.slice(1) : formula;

  expression.replace(CELL_TOKEN_PATTERN, (_match, quotedSheetName, plainSheetName, scopedToken, localToken) => {
    const resolvedSheetName = (quotedSheetName ?? plainSheetName ?? currentSheetName).trim();
    const token = scopedToken ?? localToken;

    expandReferenceToken(workbook, resolvedSheetName, token).forEach((key) => {
      dependencies.add(key);
    });

    return _match;
  });

  return dependencies;
}

export function resolveFormulaExpression(
  formula: string,
  currentSheetName: string,
  workbook: WorkbookState,
): string | null {
  const expression = formula.startsWith('=') ? formula.slice(1) : formula;

  return expression.replace(CELL_TOKEN_PATTERN, (match, quotedSheetName, plainSheetName, scopedToken, localToken) => {
    const token = scopedToken ?? localToken;
    if (token.includes(':')) {
      // Range operators are tracked for dependency, but not yet supported in arithmetic evaluator.
      return '0';
    }

    const resolvedSheetName = (quotedSheetName ?? plainSheetName ?? currentSheetName).trim();
    const expanded = expandReferenceToken(workbook, resolvedSheetName, token);
    if (expanded.length === 0) {
      return '0';
    }

    const key = expanded[0];
    const sheet = workbook.sheets[resolvedSheetName];
    if (!sheet) {
      return '0';
    }

    const [, rowIndexToken, colId] = key.split('::');
    const rowIndex = Number(rowIndexToken);
    if (!Number.isInteger(rowIndex) || !colId) {
      return match;
    }

    const row = sheet.rows[rowIndex];
    if (!row) {
      return '0';
    }

    return String(toNumber(row[colId]));
  }) ?? null;
}
