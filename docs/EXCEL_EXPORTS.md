# Excel Exports

## Coverage

Excel export is available for:

- Executive Overview;
- each analytical module;
- the complete Monthly Performance Review;
- individual monthly-report sections.

## Contract

- `.xlsx` is generated server-side;
- currency, integer, decimal, percentage, date and datetime values remain native Excel values;
- no locale-formatted number is written as text;
- every sheet freezes its header, uses filters and applies bounded column widths;
- the exported scope, period, cutoff and data source are included in metadata;
- sensitive modules preserve the same API capability checks and aggregate-suppression rules as the UI;
- temporary workbooks are deleted after the response completes;
- exports are marked private and non-cacheable.

## Workbook layout

Overview and module exports include all their analytical contracts, not only currently visible pixels. The monthly report uses separate worksheets for every management level and analysis type so users can continue analysis with pivots, formulas or Power Query without data cleaning.
