# Excel Exports

## Coverage

Excel export is available for:

- Executive Overview;
- each analytical module;
- the complete Monthly Performance Review;
- individual monthly-report sections.

This is the current XLSX coverage. CSV currently exists through the generic module inspector. Unified per-widget CSV and non-persistent PNG for chart/widget/dashboard are planned, not yet complete.

## Contract

- `.xlsx` is generated server-side;
- currency, integer, decimal, percentage, date and datetime values remain native Excel values;
- no locale-formatted number is written as text;
- every sheet freezes its header, uses filters and applies bounded column widths;
- the exported scope, period, cutoff and data source are included in metadata;
- sensitive modules preserve the same API capability checks and aggregate-suppression rules as the UI;
- temporary workbooks are deleted after the response completes;
- exports are marked private and non-cacheable.

Target contract additions: same analytical snapshot as the widget, paging/bounds, cancellation/deadline, audit, Excel formula-injection protection, sanitized filenames and the same ACL/scope ceiling at download time.

## Workbook layout

Overview and module exports include all their analytical contracts, not only currently visible pixels. The monthly report uses separate worksheets for every management level and analysis type so users can continue analysis with pivots, formulas or Power Query without data cleaning.
