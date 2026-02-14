## 2026-02-01 - CSV Injection in Admin Exports
**Vulnerability:** The admin RSVP export functionality allowed guests to inject spreadsheet formulas via fields like `name` or `dietary`. These fields were written directly to CSV without sanitization, leading to potential code execution if an admin opened the CSV in Excel.
**Learning:** Even internal admin tools can be vectors for attack if they consume user-generated content. CSV exports are a common overlook for sanitization.
**Prevention:** Always sanitize user input before writing to CSV. Prepend a single quote `'` to fields starting with `=`, `+`, `-`, or `@`.
