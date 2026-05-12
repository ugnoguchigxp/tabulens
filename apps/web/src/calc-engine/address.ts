import type { CellAddress } from './types';

const A_CHAR_CODE = 65;

export function toColumnLabel(columnIndex: number): string {
  if (columnIndex < 0) {
    throw new Error(`Column index must be non-negative: ${columnIndex}`);
  }

  let current = columnIndex;
  let label = '';
  do {
    const remainder = current % 26;
    label = String.fromCharCode(A_CHAR_CODE + remainder) + label;
    current = Math.floor(current / 26) - 1;
  } while (current >= 0);

  return label;
}

export function fromColumnLabel(label: string): number {
  if (!/^[A-Z]+$/.test(label)) {
    throw new Error(`Invalid column label: ${label}`);
  }

  let value = 0;
  for (let index = 0; index < label.length; index += 1) {
    value = value * 26 + (label.charCodeAt(index) - A_CHAR_CODE + 1);
  }

  return value - 1;
}

export function toA1Address(rowIndex: number, columnIndex: number): string {
  return `${toColumnLabel(columnIndex)}${rowIndex + 1}`;
}

export function parseA1Address(reference: string): { rowIndex: number; columnIndex: number } | null {
  const match = reference.trim().toUpperCase().match(/^([A-Z]+)([1-9][0-9]*)$/);
  if (!match) {
    return null;
  }

  return {
    columnIndex: fromColumnLabel(match[1]),
    rowIndex: Number(match[2]) - 1,
  };
}

export function toCellAddress(sheetName: string, rowIndex: number, colId: string, columnIndex: number): CellAddress {
  return {
    sheetName,
    rowIndex,
    colId,
    columnIndex,
    a1: toA1Address(rowIndex, columnIndex),
  };
}

export function getCellKey(address: Pick<CellAddress, 'sheetName' | 'rowIndex' | 'colId'>): string {
  return `${address.sheetName}::${address.rowIndex}::${address.colId}`;
}
