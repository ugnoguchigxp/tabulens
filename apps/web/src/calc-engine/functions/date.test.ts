import { describe, expect, it } from 'vitest';
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
  toExcelSerial,
  yearFn,
} from './date';

describe('date functions', () => {
  it('converts to excel serial and date components', () => {
    const serial = dateFn(2026, 5, 12);
    expect(typeof serial).toBe('number');
    expect(yearFn(serial)).toBe(2026);
    expect(monthFn(serial)).toBe(5);
    expect(dayFn(serial)).toBe(12);
  });

  it('parses date value and handles invalid date', () => {
    expect(dateValueFn('2026-05-12')).toBeGreaterThan(0);
    expect(dateValueFn('05/12/2026')).toBe('#VALUE!');
  });

  it('supports edate and eomonth', () => {
    const base = dateValueFn('2026-01-15');
    const shifted = edateFn(base, 2);
    expect(monthFn(shifted)).toBe(3);

    const endMonth = eomonthFn(base, 0);
    expect(dayFn(endMonth)).toBe(31);
  });

  it('calculates weekdays only', () => {
    const days = networkDaysFn('2026-05-11', '2026-05-15');
    expect(days).toBe(5);
    expect(networkDaysFn('bad', '2026-05-15')).toBe('#VALUE!');
  });

  it('formats text patterns', () => {
    expect(formatTextFn(1.234, '0')).toBe('1');
    expect(formatTextFn(1.234, '0.00')).toBe('1.23');
    expect(formatTextFn('2026-05-12', 'yyyy-mm-dd')).toBe('2026-05-12');
    expect(formatTextFn('2026-05-12', 'mmm')).toBe('#UNSUPPORTED');
  });

  it('supports volatile date outputs', () => {
    const now = new Date('2026-05-12T12:34:56Z');
    expect(todayFn(now)).toBe(toExcelSerial(now));
    expect(nowFn(now)).toBeGreaterThan(todayFn(now));
  });
});
