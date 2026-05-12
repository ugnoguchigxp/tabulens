const VALUE_ERROR = '#VALUE!';
const DAY_MS = 86_400_000;
const EXCEL_EPOCH_UTC = Date.UTC(1899, 11, 30);

function toDate(value: unknown): Date | null {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return new Date(EXCEL_EPOCH_UTC + value * DAY_MS);
  }
  if (value instanceof Date) {
    return new Date(value.getTime());
  }
  if (typeof value === 'string') {
    const iso = value.match(/^\d{4}-\d{2}-\d{2}$/);
    if (!iso) return null;
    const parsed = new Date(`${value}T00:00:00Z`);
    if (Number.isNaN(parsed.getTime())) return null;
    return parsed;
  }
  return null;
}

export function toExcelSerial(date: Date): number {
  return Math.floor((Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) - EXCEL_EPOCH_UTC) / DAY_MS);
}

export function dateFn(year: unknown, month: unknown, day: unknown): unknown {
  const y = Number(year);
  const m = Number(month);
  const d = Number(day);
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return VALUE_ERROR;
  const value = new Date(Date.UTC(y, m - 1, d));
  return toExcelSerial(value);
}

export function dateValueFn(value: unknown): unknown {
  const parsed = toDate(value);
  if (!parsed) return VALUE_ERROR;
  return toExcelSerial(parsed);
}

export function yearFn(value: unknown): unknown {
  const parsed = toDate(value);
  if (!parsed) return VALUE_ERROR;
  return parsed.getUTCFullYear();
}

export function monthFn(value: unknown): unknown {
  const parsed = toDate(value);
  if (!parsed) return VALUE_ERROR;
  return parsed.getUTCMonth() + 1;
}

export function dayFn(value: unknown): unknown {
  const parsed = toDate(value);
  if (!parsed) return VALUE_ERROR;
  return parsed.getUTCDate();
}

export function edateFn(value: unknown, months: unknown): unknown {
  const parsed = toDate(value);
  const delta = Number(months);
  if (!parsed || !Number.isFinite(delta)) return VALUE_ERROR;
  const next = new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth() + delta, parsed.getUTCDate()));
  return toExcelSerial(next);
}

export function eomonthFn(value: unknown, months: unknown): unknown {
  const parsed = toDate(value);
  const delta = Number(months);
  if (!parsed || !Number.isFinite(delta)) return VALUE_ERROR;
  const next = new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth() + delta + 1, 0));
  return toExcelSerial(next);
}

export function networkDaysFn(startValue: unknown, endValue: unknown): unknown {
  const start = toDate(startValue);
  const end = toDate(endValue);
  if (!start || !end) return VALUE_ERROR;

  const direction = start <= end ? 1 : -1;
  let current = new Date(start.getTime());
  let count = 0;
  while ((direction > 0 && current <= end) || (direction < 0 && current >= end)) {
    const day = current.getUTCDay();
    if (day !== 0 && day !== 6) count += direction;
    current = new Date(current.getTime() + direction * DAY_MS);
  }
  return count;
}

export function formatTextFn(value: unknown, format: unknown): unknown {
  const pattern = String(format ?? '');
  if (pattern === '0' || pattern === '0.00') {
    const number = Number(value);
    if (!Number.isFinite(number)) return VALUE_ERROR;
    return pattern === '0' ? String(Math.round(number)) : number.toFixed(2);
  }
  if (pattern === 'yyyy-mm-dd') {
    const parsed = toDate(value);
    if (!parsed) return VALUE_ERROR;
    const yyyy = parsed.getUTCFullYear();
    const mm = String(parsed.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(parsed.getUTCDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }
  return '#UNSUPPORTED';
}

export function todayFn(now: Date): number {
  return toExcelSerial(now);
}

export function nowFn(now: Date): number {
  return (now.getTime() - EXCEL_EPOCH_UTC) / DAY_MS;
}
