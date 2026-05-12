const VALUE_ERROR = '#VALUE!';

function asText(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value);
}

export function concatFn(...args: unknown[]): string {
  return args.map((arg) => asText(arg)).join('');
}

export function leftFn(value: unknown, count: unknown = 1): unknown {
  const text = asText(value);
  const size = Number(count);
  if (!Number.isInteger(size) || size < 0) return VALUE_ERROR;
  return text.slice(0, size);
}

export function rightFn(value: unknown, count: unknown = 1): unknown {
  const text = asText(value);
  const size = Number(count);
  if (!Number.isInteger(size) || size < 0) return VALUE_ERROR;
  return size === 0 ? '' : text.slice(-size);
}

export function midFn(value: unknown, start: unknown, count: unknown): unknown {
  const text = asText(value);
  const offset = Number(start);
  const size = Number(count);
  if (!Number.isInteger(offset) || !Number.isInteger(size) || offset < 1 || size < 0) return VALUE_ERROR;
  return text.slice(offset - 1, offset - 1 + size);
}

export function lenFn(value: unknown): number {
  return asText(value).length;
}

export function trimFn(value: unknown): string {
  return asText(value).replace(/\s+/g, ' ').trim();
}

export function upperFn(value: unknown): string {
  return asText(value).toUpperCase();
}

export function lowerFn(value: unknown): string {
  return asText(value).toLowerCase();
}

export function substituteFn(text: unknown, oldText: unknown, newText: unknown): string {
  return asText(text).split(asText(oldText)).join(asText(newText));
}
