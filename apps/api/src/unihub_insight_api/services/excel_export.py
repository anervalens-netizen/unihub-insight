from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import xlsxwriter
from pydantic import BaseModel

from unihub_insight_api.domain import (
    AnalyticalSnapshot,
    DatasetDimension,
    MetricDefinition,
    MetricUnit,
    ModuleAnalyticsResponse,
    OverviewResponse,
    QueryDataset,
    QueryExecutionMeta,
    SourceMetadata,
    WidgetQuery,
)
from unihub_insight_api.domain.monthly_review import MonthlyReviewResponse

ExcelKind = Literal["text", "integer", "decimal", "currency", "percent", "date", "datetime"]


@dataclass(frozen=True)
class Column:
    key: str
    label: str
    kind: ExcelKind = "text"
    width: int = 14


class ExcelBuilder:
    def __init__(self, prefix: str) -> None:
        descriptor, path = tempfile.mkstemp(prefix=f"unihub-insight-{prefix}-", suffix=".xlsx")
        os.close(descriptor)
        self.path = Path(path)
        self.workbook = xlsxwriter.Workbook(
            self.path,
            {"constant_memory": True, "strings_to_numbers": False},
        )
        self.header = self.workbook.add_format(
            {
                "bold": True,
                "font_color": "#FFFFFF",
                "bg_color": "#17324D",
                "border": 1,
                "border_color": "#D9E2EC",
                "align": "center",
                "valign": "vcenter",
            }
        )
        self.text = self.workbook.add_format({"valign": "top"})
        self.integer = self.workbook.add_format({"num_format": "#,##0", "valign": "top"})
        self.decimal = self.workbook.add_format({"num_format": "#,##0.00", "valign": "top"})
        self.currency = self.workbook.add_format({"num_format": '#,##0.00 "RON"', "valign": "top"})
        self.percent = self.workbook.add_format({"num_format": "0.00%", "valign": "top"})
        self.date = self.workbook.add_format({"num_format": "yyyy-mm-dd", "valign": "top"})
        self.datetime = self.workbook.add_format({"num_format": "yyyy-mm-dd hh:mm:ss", "valign": "top"})

    def close(self) -> Path:
        self.workbook.close()
        return self.path

    def add_sheet(
        self,
        name: str,
        columns: Sequence[Column],
        rows: Iterable[BaseModel | Mapping[str, Any]],
    ) -> None:
        sheet = self.workbook.add_worksheet(self._sheet_name(name))
        sheet.freeze_panes(1, 0)
        sheet.set_row(0, 28)
        for index, column in enumerate(columns):
            sheet.write(0, index, column.label, self.header)
            sheet.set_column(index, index, min(max(column.width, 8), 48))
        row_index = 1
        for item in rows:
            values = item.model_dump(mode="python") if isinstance(item, BaseModel) else item
            for column_index, column in enumerate(columns):
                self._write_cell(
                    sheet,
                    row_index,
                    column_index,
                    values.get(column.key),
                    column.kind,
                )
            row_index += 1
        if row_index > 1:
            sheet.autofilter(0, 0, row_index - 1, len(columns) - 1)
        sheet.set_landscape()
        sheet.fit_to_pages(1, 0)

    def add_notes(self, name: str, rows: Sequence[tuple[str, Any]]) -> None:
        sheet = self.workbook.add_worksheet(self._sheet_name(name))
        sheet.set_column(0, 0, 28)
        sheet.set_column(1, 1, 88)
        sheet.write_row(0, 0, ["Câmp", "Valoare"], self.header)
        for index, (label, value) in enumerate(rows, start=1):
            sheet.write(index, 0, label, self.text)
            self._write_cell(sheet, index, 1, value, "text")

    @staticmethod
    def _sheet_name(value: str) -> str:
        cleaned = "".join(character for character in value if character not in "[]:*?/\\")
        return cleaned[:31] or "Date"

    def _format(self, kind: ExcelKind) -> xlsxwriter.format.Format:
        return {
            "text": self.text,
            "integer": self.integer,
            "decimal": self.decimal,
            "currency": self.currency,
            "percent": self.percent,
            "date": self.date,
            "datetime": self.datetime,
        }[kind]

    def _write_cell(
        self,
        sheet: xlsxwriter.worksheet.Worksheet,
        row: int,
        column: int,
        value: Any,
        kind: ExcelKind,
    ) -> None:
        if value is None:
            sheet.write_blank(row, column, None, self._format(kind))
            return
        if isinstance(value, StrEnum):
            value = value.value
        if isinstance(value, Decimal):
            value = float(value)
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
            value = f"'{value}"
        if kind == "percent" and isinstance(value, int | float):
            value /= 100
        if kind in {"date", "datetime"} and isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                sheet.write(row, column, value, self.text)
                return
        if isinstance(value, datetime):
            sheet.write_datetime(row, column, value.replace(tzinfo=None), self._format(kind))
        elif isinstance(value, date):
            sheet.write_datetime(
                row,
                column,
                datetime.combine(value, datetime.min.time()),
                self._format(kind),
            )
        elif isinstance(value, bool):
            sheet.write_boolean(row, column, value, self._format(kind))
        elif isinstance(value, int | float):
            sheet.write_number(row, column, float(value), self._format(kind))
        elif isinstance(value, (list, tuple, set, frozenset)):
            sheet.write(row, column, ", ".join(str(item) for item in value), self.text)
        else:
            sheet.write(row, column, str(value), self._format(kind))


def _query_column(dimension: DatasetDimension, metric: MetricDefinition) -> Column:
    kind: ExcelKind = "text"
    if dimension.kind == "integer":
        kind = "integer"
    elif dimension.kind == "number":
        if dimension.role in {"value", "comparison", "target"}:
            unit_kinds: dict[MetricUnit, ExcelKind] = {
                MetricUnit.CURRENCY: "currency",
                MetricUnit.PERCENT: "percent",
                MetricUnit.INTEGER: "integer",
                MetricUnit.DECIMAL: "decimal",
            }
            kind = unit_kinds[metric.unit]
        else:
            kind = "decimal"
    return Column(dimension.id, dimension.label, kind, 22)


def query_workbook(
    dataset: QueryDataset,
    meta: QueryExecutionMeta,
    snapshot: AnalyticalSnapshot,
    query: WidgetQuery,
    metric: MetricDefinition,
) -> Path:
    """Build a bounded per-widget workbook from the exact inspected query snapshot."""
    builder = ExcelBuilder("widget")
    builder.add_sheet(
        "Date",
        [_query_column(dimension, metric) for dimension in dataset.dimensions],
        dataset.rows,
    )
    notes: list[tuple[str, Any]] = [
        ("Snapshot analitic", snapshot.id),
        ("Perioadă", meta.period),
        ("Scope", meta.scope_label),
        ("Widget", query.widget_id),
        ("Modul", query.module.value),
        ("Metrică", metric.id),
        ("Metric version", metric.version),
        ("Query contract version", query.query_contract_version),
        ("Dimensiuni", query.dimensions),
        ("Interval", f"{query.time_range.start} → {query.time_range.end}" if query.time_range else meta.period),
        ("Comparații", tuple(item.value for item in query.comparisons)),
        ("Warnings", meta.warnings),
        ("Generat", meta.generated_at),
    ]
    notes.extend(_source_notes(meta.sources))
    builder.add_notes("Metadata", notes)
    return builder.close()


def _source_notes(sources: Mapping[Any, SourceMetadata]) -> list[tuple[str, Any]]:
    notes: list[tuple[str, Any]] = []
    for domain, source in sorted(sources.items(), key=lambda item: str(item[0])):
        prefix = f"Sursă {domain}"
        notes.extend(
            [
                (prefix, source.source),
                (f"{prefix} status", source.status.value),
                (f"{prefix} perioadă", source.period),
                (f"{prefix} cutoff", source.cutoff),
                (f"{prefix} as of", source.as_of),
                (f"{prefix} final", source.is_final),
                (f"{prefix} coverage numărător", source.coverage_numerator),
                (f"{prefix} coverage numitor", source.coverage_denominator),
                (f"{prefix} generație", source.source_generation),
                (f"{prefix} autoritate", source.authority),
                (f"{prefix} head", source.authority_head),
                (f"{prefix} contract version", source.contract_version),
                (f"{prefix} rule version", source.rule_version),
                (f"{prefix} produs la", source.produced_at),
                (f"{prefix} warnings", source.warnings),
            ]
        )
    return notes


def overview_workbook(data: OverviewResponse) -> Path:
    builder = ExcelBuilder("overview")
    builder.add_notes(
        "Metadata",
        [
            ("Perioadă", data.meta.period),
            ("Scope", data.meta.scope_label),
            ("Cutoff", data.meta.as_of),
            ("Lună finală", data.meta.is_final),
            ("Sursă", data.meta.source),
            ("Snapshot analitic", data.meta.analytical_snapshot_id),
            ("Generat", data.meta.generated_at),
            *_source_notes(data.meta.sources),
        ],
    )
    builder.add_sheet(
        "KPI",
        [
            Column("id", "ID", width=24),
            Column("label", "Indicator", width=32),
            Column("value", "Valoare", "decimal", 18),
            Column("unit", "Unitate", width=14),
            Column("delta_pct", "Delta", "percent", 14),
            Column("delta_label", "Reper", width=24),
            Column("supporting_value", "Valoare suport", "decimal", 18),
            Column("supporting_label", "Etichetă suport", width=28),
            Column("risk", "Risc", width=14),
        ],
        data.kpis,
    )
    builder.add_sheet(
        "Evoluție zilnică",
        [
            Column("day", "Zi", "integer", 8),
            Column("sales", "Vânzări", "currency", 18),
            Column("target_pace", "Ritm target", "currency", 18),
            Column("forecast", "Forecast", "currency", 18),
            Column("comparison", "Comparație", "currency", 18),
        ],
        data.daily,
    )
    builder.add_sheet(
        "Contribuție",
        [
            Column("id", "ID", width=20),
            Column("label", "Entitate", width=34),
            Column("value", "Vânzări", "currency", 18),
            Column("share_pct", "Pondere", "percent", 14),
        ],
        data.contribution,
    )
    builder.add_sheet(
        "Performanță",
        [
            Column("id", "ID", width=18),
            Column("label", "Entitate", width=34),
            Column("context", "Context", width=42),
            Column("sales", "Vânzări", "currency", 18),
            Column("target", "Target", "currency", 18),
            Column("progress_pct", "Realizare", "percent", 14),
            Column("delta_pct", "Delta", "percent", 14),
            Column("risk", "Risc", width=14),
        ],
        data.performance,
    )
    builder.add_sheet(
        "Alerte",
        [
            Column("severity", "Severitate", width=14),
            Column("title", "Titlu", width=36),
            Column("description", "Descriere", width=48),
            Column("entity_label", "Entitate", width=32),
        ],
        data.alerts,
    )
    return builder.close()


def module_workbook(data: ModuleAnalyticsResponse) -> Path:
    builder = ExcelBuilder(data.module.value)
    builder.add_notes(
        "Metadata",
        [
            ("Modul", data.title),
            ("Perioadă", data.meta.period),
            ("Scope", data.meta.scope_label),
            ("Cutoff", data.meta.as_of),
            ("Sursă", data.meta.source),
            ("Snapshot analitic", data.meta.analytical_snapshot_id),
            ("Capabilitate", data.required_capability.value),
            *_source_notes(data.meta.sources),
        ],
    )
    builder.add_sheet(
        "KPI",
        [
            Column("id", "ID", width=28),
            Column("label", "Indicator", width=32),
            Column("value", "Valoare", "decimal", 18),
            Column("unit", "Unitate", width=14),
            Column("delta_pct", "Delta", "percent", 14),
            Column("supporting_value", "Valoare suport", "decimal", 18),
            Column("supporting_label", "Etichetă suport", width=28),
            Column("risk", "Risc", width=14),
        ],
        data.kpis,
    )
    builder.add_sheet(
        "Trend",
        [
            Column("key", "Cheie", width=14),
            Column("label", "Perioadă", width=16),
            Column("primary", data.axes[0].label if data.axes else "Principal", "decimal", 18),
            Column("comparison", "Comparație", "decimal", 18),
            Column("target", "Target", "decimal", 18),
            Column("secondary", data.axes[1].label if len(data.axes) > 1 else "Secundar", "decimal", 18),
            Column("is_estimate", "Estimat", width=12),
        ],
        data.trend,
    )
    builder.add_sheet(
        "Distribuție",
        [
            Column("id", "ID", width=20),
            Column("label", "Entitate", width=36),
            Column("value", "Valoare", "decimal", 18),
            Column("share_pct", "Pondere", "percent", 14),
        ],
        data.distribution,
    )
    builder.add_sheet(
        "Detaliu",
        [
            Column("id", "ID", width=22),
            Column("label", "Entitate", width=36),
            Column("context", "Context", width=44),
            Column("primary", data.axes[0].label if data.axes else "Principal", "decimal", 18),
            Column("secondary", data.axes[1].label if len(data.axes) > 1 else "Secundar", "decimal", 18),
            Column("tertiary", data.axes[2].label if len(data.axes) > 2 else "Terțiar", "decimal", 18),
            Column("progress_pct", "Progres", "percent", 14),
            Column("delta_pct", "Delta", "percent", 14),
            Column("risk", "Risc", width=14),
        ],
        data.breakdown,
    )
    builder.add_sheet(
        "Matrice",
        [
            Column("x", "Perioadă", width=16),
            Column("y", "Entitate", width=36),
            Column("value", "Valoare", "decimal", 18),
            Column("label", "Etichetă", width=20),
            Column("risk", "Risc", width=14),
        ],
        data.matrix,
    )
    builder.add_sheet(
        "Calendar",
        [
            Column("date", "Dată", width=14),
            Column("sales", "Vânzări", "currency", 18),
            Column("net_quantity", "Cantitate netă", "integer", 16),
            Column("positive_quantity", "Cantitate pozitivă", "integer", 18),
            Column("return_quantity", "Cantitate retur", "integer", 16),
            Column("receipt_count", "Bonuri", "integer", 14),
            Column("receipt_2plus_count", "Bonuri 2+", "integer", 14),
            Column("observed_store_count", "Magazine observate", "integer", 20),
            Column("coverage_state", "Coverage", width=14),
        ],
        data.calendar,
    )
    builder.add_sheet(
        "Alerte",
        [
            Column("severity", "Severitate", width=14),
            Column("title", "Titlu", width=36),
            Column("description", "Descriere", width=48),
            Column("entity_label", "Entitate", width=32),
        ],
        data.alerts,
    )
    return builder.close()


def monthly_review_workbook(
    data: MonthlyReviewResponse,
    section: str = "all",
) -> Path:
    builder = ExcelBuilder("monthly-review")
    selected = section.casefold()

    def enabled(name: str) -> bool:
        return selected == "all" or selected == name.casefold()

    if enabled("summary"):
        builder.add_notes(
            "Metadata",
            [
                ("Perioadă", data.meta.period),
                ("Scope", data.meta.scope_label),
                ("Cutoff", data.meta.as_of),
                ("Lună finală", data.meta.is_final),
                ("Reper recent", f"{data.recent_months} luni"),
                ("Sursă", data.meta.source),
                ("Snapshot analitic", data.meta.analytical_snapshot_id),
                ("Generat", data.meta.generated_at),
                *_source_notes(data.meta.sources),
            ],
        )
        builder.add_sheet(
            "Sinteză",
            [
                Column("id", "ID", width=24),
                Column("label", "Indicator", width=32),
                Column("current", "Curent", "decimal", 18),
                Column("previous_year", "Anul trecut", "decimal", 18),
                Column("previous_month", "Luna precedentă", "decimal", 18),
                Column("recent_average", "Media recentă", "decimal", 18),
                Column("target", "Target / reper", "decimal", 18),
                Column("yoy_delta", "Delta YoY", "percent", 14),
                Column("mom_delta", "Delta MoM", "percent", 14),
                Column("recent_delta", "Delta recent", "percent", 14),
                Column("target_delta", "Delta target", "percent", 14),
                Column("delta_kind", "Tip delta", width=20),
                Column("unit", "Unitate", width=14),
            ],
            data.executive,
        )
        builder.add_sheet(
            "Driveri",
            [
                Column("basis", "Reper", width=34),
                Column("baseline_sales", "Vânzări reper", "currency", 18),
                Column("current_sales", "Vânzări curente", "currency", 18),
                Column("sales_difference", "Diferență", "currency", 18),
                Column("receipts_effect", "Efect bonuri", "currency", 18),
                Column("units_per_receipt_effect", "Efect produse/bon", "currency", 20),
                Column("value_per_unit_effect", "Efect valoare/produs", "currency", 22),
            ],
            data.drivers,
        )
    if enabled("trend"):
        builder.add_sheet(
            "Trend",
            [
                Column("period", "Perioadă", width=14),
                Column("sales", "Vânzări", "currency", 18),
                Column("units", "Unități", "integer", 14),
                Column("receipts", "Bonuri", "integer", 14),
                Column("target", "Target", "currency", 18),
                Column("target_pct", "Realizare", "percent", 14),
                Column("average_receipt", "Valoare medie bon", "currency", 18),
                Column("return_rate_pct", "Rată retur", "percent", 14),
            ],
            data.trend,
        )
    if enabled("trend") or selected == "all":
        builder.add_sheet(
            "Sezonalitate",
            [
                Column("year", "An", "integer", 10),
                Column("previous_period", "Lună anterioară", width=16),
                Column("current_period", "Lună analizată", width=16),
                Column("sales_lift_pct", "Lift vânzări", "percent", 16),
                Column("units_lift_pct", "Lift unități", "percent", 16),
                Column("receipts_lift_pct", "Lift bonuri", "percent", 16),
                Column(
                    "sales_per_store_day_lift_pct",
                    "Lift vânzări / zi-magazin",
                    "percent",
                    24,
                ),
                Column("store_count", "Magazine cohortă", "integer", 16),
                Column("is_current", "An curent", width=12),
            ],
            data.seasonality,
        )
    performance_columns = [
        Column("id", "ID", width=20),
        Column("label", "Entitate", width=36),
        Column("context", "Context", width=46),
        Column("sales", "Vânzări", "currency", 18),
        Column("target", "Target", "currency", 18),
        Column("target_pct", "Realizare", "percent", 14),
        Column("previous_year_sales", "Vânzări anul trecut", "currency", 20),
        Column("previous_month_sales", "Vânzări luna precedentă", "currency", 22),
        Column("recent_average_sales", "Media recentă", "currency", 18),
        Column("yoy_pct", "YoY", "percent", 14),
        Column("mom_pct", "MoM", "percent", 14),
        Column("recent_pct", "Vs recent", "percent", 14),
        Column("units", "Unități", "integer", 14),
        Column("receipts", "Bonuri", "integer", 14),
        Column("average_receipt", "Valoare medie bon", "currency", 18),
        Column("units_per_receipt", "Produse/bon", "decimal", 14),
        Column("value_per_unit", "Valoare/produs", "currency", 18),
        Column("bon2acc_pct", "Bon 2+", "percent", 14),
        Column("focus_pct", "Focus", "percent", 14),
        Column("return_rate_pct", "Rată retur", "percent", 14),
        Column("working_days", "Zile active", "decimal", 14),
        Column("consistency_pct", "Consistență", "percent", 14),
        Column("performance_score", "Scor", "decimal", 12),
        Column("status", "Status", width=18),
        Column("primary_driver", "Driver principal", width=28),
        Column("primary_driver_impact", "Impact driver", "currency", 18),
        Column("driver_basis", "Reper driver", width=18),
    ]
    for key, title, rows in (
        ("companies", "Companii", data.companies),
        ("managers", "Manageri", data.managers),
        ("stores", "Magazine", data.stores),
        ("agents", "Agenți", data.agents),
    ):
        if enabled(key):
            builder.add_sheet(title, performance_columns, rows)
    product_columns = [
        Column("id", "Cod", width=20),
        Column("label", "Produs / categorie", width=48),
        Column("brand", "Brand", width=20),
        Column("category", "Categorie", width=28),
        Column("sales", "Vânzări", "currency", 18),
        Column("previous_year_sales", "Anul trecut", "currency", 18),
        Column("recent_average_sales", "Media recentă", "currency", 18),
        Column("yoy_pct", "YoY", "percent", 14),
        Column("recent_pct", "Vs recent", "percent", 14),
        Column("units", "Unități", "integer", 14),
        Column("previous_year_units", "Unități anul trecut", "integer", 18),
        Column("distribution", "Distribuție", "integer", 14),
        Column("previous_year_distribution", "Distribuție anul trecut", "integer", 20),
        Column("return_rate_pct", "Rată retur", "percent", 14),
        Column("previous_year_return_rate_pct", "Rată retur anul trecut", "percent", 20),
        Column("impact_yoy", "Impact YoY", "currency", 18),
        Column("impact_recent", "Impact recent", "currency", 18),
        Column("score", "Scor impact", "currency", 18),
        Column("status", "Status", width=18),
    ]
    if enabled("categories"):
        builder.add_sheet("Categorii", product_columns, data.categories)
    if enabled("products"):
        builder.add_sheet("Produse", product_columns, data.products)
    if enabled("returns"):
        builder.add_sheet(
            "Retururi",
            [
                Column("entity_type", "Tip", width=14),
                Column("id", "ID", width=20),
                Column("label", "Entitate", width=48),
                Column("context", "Context", width=40),
                Column("current_value", "Valoare retur", "currency", 18),
                Column("previous_year_value", "Anul trecut", "currency", 18),
                Column("recent_average_value", "Media recentă", "currency", 18),
                Column("current_rate_pct", "Rată curentă", "percent", 14),
                Column("previous_year_rate_pct", "Rată anul trecut", "percent", 18),
                Column("recent_rate_pct", "Rată recentă", "percent", 14),
                Column("yoy_rate_delta_pp", "Delta YoY", "percent", 14),
                Column("recent_rate_delta_pp", "Delta recent", "percent", 14),
                Column("status", "Status", width=18),
            ],
            data.returns,
        )
    if enabled("methodology") or selected == "all":
        builder.add_notes(
            "Metodologie",
            [(f"Regula {index}", value) for index, value in enumerate(data.methodology, 1)],
        )
    if selected == "all":
        builder.add_sheet(
            "Alerte",
            [
                Column("severity", "Severitate", width=14),
                Column("title", "Titlu", width=36),
                Column("description", "Descriere", width=58),
                Column("entity_label", "Entitate", width=32),
            ],
            data.alerts,
        )
    return builder.close()
