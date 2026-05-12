# Supported Formulas

## v0 baseline

- Arithmetic: `+`, `-`, `*`, `/`
- Logic: `IF`, `AND`, `OR`, `NOT`
- Numeric: `SUM`, `AVERAGE`, `MIN`, `MAX`, `COUNT`, `ROUND`, `ABS`

## v1 lookup/reference

- `INDEX`
- `MATCH` (exact match only)
- `VLOOKUP` (exact match only)
- `XLOOKUP` (exact match only)

## v1.2 text/date

- Text: `CONCAT`, `LEFT`, `RIGHT`, `MID`, `LEN`, `TRIM`, `UPPER`, `LOWER`, `SUBSTITUTE`, `TEXT`
- Date: `DATE`, `DATEVALUE`, `YEAR`, `MONTH`, `DAY`, `EDATE`, `EOMONTH`, `NETWORKDAYS`

## v1.3 volatile / workflow

- Volatile: `NOW`, `TODAY`, `RAND`, `RANDBETWEEN`
- Workflow: `PREDICT`

## Current compatibility notes

- `MATCH`, `VLOOKUP`, `XLOOKUP` の approximate match は未対応です。未対応指定は `#UNSUPPORTED` を返します。
- `TEXT` は `0`, `0.00`, `yyyy-mm-dd` のみ対応です。
- 対応外関数は `#UNSUPPORTED` を返します。
