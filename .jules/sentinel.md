## 2025-02-17 - [CSV Injection Vulnerability in Exports]
**Vulnerability:** User-controlled input (names, dietary restrictions) was directly written to CSV files using Python's `csv` module, allowing Formula Injection (CSV Injection) attacks if the input starts with `=`, `@`, `+`, or `-`.
**Learning:** Using raw `csv.writer` bypasses application-level security controls. The project already had a secure utility `CSVExportUtils` but it wasn't consistently used.
**Prevention:** All CSV generation MUST use `app.utils.csv_export.CSVExportUtils.generate_csv_content` which implements sanitization (prepending `'` to formulas) and consistent formatting (BOM for Excel). Avoid direct `csv` module usage in service layers.
