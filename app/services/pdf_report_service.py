"""PDF rendering for the therapy-data report.

Uses WeasyPrint + Jinja2. The aggregation logic stays in
``adherence_service``; this module only does presentation: it formats
the input ``TherapyDataReport`` for the template and produces SVG
chart fragments (bars, monthly bars, sparklines, parameter lines).

Heavy imports (WeasyPrint, Jinja2) live at module level so the cost
is paid once per process. They are not imported by other services,
so unrelated routes don't pay the startup cost.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.schemas.adherence import (
    MedicationBar,
    MedicationMonthlyAggregate,
    MedicationSparklinePoint,
    ParameterPoint,
    ParameterSeries,
)
from app.schemas.report import TherapyDataReport

# ---------------------------------------------------------------------------
# Constants & Jinja env
# ---------------------------------------------------------------------------
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

ITALIAN_MONTHS = [
    "gen", "feb", "mar", "apr", "mag", "giu",
    "lug", "ago", "set", "ott", "nov", "dic",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def render(report: TherapyDataReport, profile_meta: dict[str, Any]) -> bytes:
    """Render the report into PDF bytes (A4)."""
    # Lazy import: WeasyPrint loads native libs (Pango/Cairo/GDK) at
    # import time. On dev machines without those installed, importing
    # at module top breaks unrelated tests (HTML-only smoke, etc.).
    from weasyprint import HTML

    css_text = (TEMPLATES_DIR / "report_clinico.css").read_text(encoding="utf-8")
    template = _env.get_template("report_clinico.html")
    context = _build_context(report, profile_meta, css_text)
    html_str = template.render(**context)
    return HTML(string=html_str, base_url=str(TEMPLATES_DIR)).write_pdf()


def render_html(report: TherapyDataReport, profile_meta: dict[str, Any]) -> str:
    """Render the report to HTML (used by tests + preview)."""
    css_text = (TEMPLATES_DIR / "report_clinico.css").read_text(encoding="utf-8")
    template = _env.get_template("report_clinico.html")
    context = _build_context(report, profile_meta, css_text)
    return template.render(**context)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------
def _build_context(
    report: TherapyDataReport,
    profile_meta: dict[str, Any],
    css_text: str,
) -> dict[str, Any]:
    period_label = _format_period_label(report.period.from_, report.period.to)
    eyebrow = _format_eyebrow(report)
    generated_label = _format_generated(report.generated_at)
    tracked_meds = _tracked_meds(report)
    tracked_params = _tracked_params(report)
    notes = _format_notes(report)
    adherence = _format_adherence(report)
    parameters = _format_parameters(report)
    return {
        "css": css_text,
        "profile_name": profile_meta.get("display_name") or "—",
        "eyebrow": eyebrow,
        "period_label": period_label,
        "generated_label": generated_label,
        "tracked_meds": tracked_meds,
        "tracked_params": tracked_params,
        "adherence": adherence,
        "parameters": parameters,
        "notes": notes,
        "macros": _Macros(),
    }


# ---------------------------------------------------------------------------
# Header / labels
# ---------------------------------------------------------------------------
def _format_eyebrow(report: TherapyDataReport) -> str:
    span_days = (report.period.to - report.period.from_).days + 1
    if report.period.kind == "all":
        return "Riepilogo terapie · Pro · Tutto lo storico".upper()
    if report.period.kind == "12mo":
        return "Riepilogo terapie · Pro · 12 mesi".upper()
    # Custom ≥150 days → "Pro · N mesi"
    if report.period.kind == "custom" and span_days >= 150:
        months = round(span_days / 30)
        return f"Riepilogo terapie · Pro · {months} mesi".upper()
    return "Riepilogo terapie".upper()


def _format_period_label(start: date, end: date) -> str:
    same_year = start.year == end.year
    start_part = f"{start.day} {ITALIAN_MONTHS[start.month - 1]}" + ("" if same_year else f" {start.year}")
    end_part = f"{end.day} {ITALIAN_MONTHS[end.month - 1]} {end.year}"
    return f"{start_part} – {end_part}"


def _format_generated(dt: datetime) -> str:
    return f"{dt.day} {ITALIAN_MONTHS[dt.month - 1]} {dt.year} · {dt.strftime('%H:%M')}"


def _tracked_meds(report: TherapyDataReport) -> list[dict[str, str]]:
    """Build the FARMACI summary list with dosage + schedule info.

    The reference PDFs surface dosing times directly in the FARMACI
    column (e.g. "Eutirox 50 mcg · 06:30"). We pack that info into the
    meta column when present.
    """
    if not report.adherence:
        return []
    out = []
    for s in report.adherence.medications:
        principle = s.principle or ""
        sched = s.schedule_label or ""
        if principle and sched:
            meta = f"{principle} · {sched}"
        else:
            meta = principle or sched
        out.append({"name": s.name, "dose_label": meta})
    return out


def _tracked_params(report: TherapyDataReport) -> list[dict[str, str]]:
    if not report.parameters:
        return []
    out = []
    for p in report.parameters:
        out.append({"name": p.name, "frequency": _frequency_label(p)})
    return out


def _frequency_label(param: ParameterSeries) -> str:
    n = len(param.points)
    if n == 0:
        return "—"
    span_days = max(
        1,
        (param.points[-1].recorded_at.date() - param.points[0].recorded_at.date()).days + 1,
    )
    if n / span_days >= 0.9:
        return "1×/giorno"
    per_week = n / (span_days / 7)
    if per_week >= 2.5:
        return f"{round(per_week)}×/sett"
    if per_week >= 0.7:
        return "1×/sett"
    return f"{n} misurazioni"


# ---------------------------------------------------------------------------
# Adherence / parameters / notes pre-formatting
# ---------------------------------------------------------------------------
def _format_adherence(report: TherapyDataReport):
    """Pass-through but exposes attrs the template reads directly."""
    return report.adherence


def _format_parameters(report: TherapyDataReport):
    """Format parameter series for the template.

    Pulls target ranges from the predefined catalog and computes a
    trend delta (last − first) when meaningful (numericSingle with at
    least 2 points and span ≥ 14 days).
    """
    from app.services.parameters_service import get_predefined  # local

    if not report.parameters:
        return []
    out = []
    for p in report.parameters:
        last = p.points[-1] if p.points else None
        first = p.points[0] if p.points else None
        meta = get_predefined(p.parameter_key) or {}
        if last is None:
            last_value = "—"
        elif p.value_type == "numericDouble":
            v1 = "" if last.v1 is None else _format_number(last.v1)
            v2 = "" if last.v2 is None else _format_number(last.v2)
            last_value = f"{v1}/{v2}" if v1 and v2 else (v1 or v2 or "—")
        else:
            last_value = _format_number(last.v1) if last.v1 is not None else "—"

        # Trend delta — numericSingle, ≥ 2 weeks span, ≥ 1 decimal of
        # actual change (skip the noise of "0 kg in 3 sett").
        trend_label: str | None = None
        if (
            p.value_type == "numericSingle"
            and first is not None and last is not None
            and first.v1 is not None and last.v1 is not None
            and (last.recorded_at - first.recorded_at).days >= 14
        ):
            delta = last.v1 - first.v1
            decimals = int(meta.get("decimals", 1))
            quantum = 10.0 ** -decimals
            if abs(delta) >= quantum / 2:
                sign = "+" if delta > 0 else "−"
                magnitude = _format_number(abs(delta))
                unit = p.unit or ""
                span_days = (last.recorded_at - first.recorded_at).days
                span_label = _humanize_span(span_days)
                trend_label = f"{sign}{magnitude} {unit} in {span_label}".strip()

        target = _target_lines_for(p, meta)
        out.append({
            "parameter_key": p.parameter_key,
            "name": p.name,
            "unit": p.unit,
            "value_type": p.value_type,
            "labels": p.labels,
            "points": p.points,
            "last_value": last_value,
            "target_label": meta.get("target_label"),
            "target_lines": target,
            "trend_label": trend_label,
        })
    return out


def _humanize_span(days: int) -> str:
    if days < 21:
        return f"{days} giorni"
    weeks = days // 7
    if weeks < 8:
        return f"{weeks} sett"
    months = round(days / 30)
    return f"{months} mesi"


def _target_lines_for(p, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Return one or two reference lines to draw on the chart, in
    the same Y axis as the data. Each entry: {value, color, label}.
    """
    lines: list[dict[str, Any]] = []
    if p.value_type == "numericDouble":
        if (v := meta.get("target_high_v1")) is not None:
            lines.append({"value": v, "color": "#2B7DD4", "axis": 1})
        if (v := meta.get("target_high_v2")) is not None:
            lines.append({"value": v, "color": "#1D9E75", "axis": 2})
    else:
        for key, color in (("target_high", "#888780"), ("target_low", "#888780")):
            v = meta.get(key)
            if v is not None:
                lines.append({"value": v, "color": color, "axis": 1})
    return lines


def _format_number(v: float) -> str:
    """Italian locale: use comma as decimal separator (76,3 not 76.3)."""
    if v == int(v):
        return str(int(v))
    return f"{v:.1f}".replace(".", ",")


def _format_notes(report: TherapyDataReport) -> list[dict[str, str]]:
    if not report.notes:
        return []
    out = []
    for n in report.notes:
        out.append({
            "medication_name": n.medication_name,
            "when_label": _format_when(n.due_at),
            "snippet": n.snippet,
        })
    return out


def _format_when(dt: datetime) -> str:
    return f"{dt.day} {ITALIAN_MONTHS[dt.month - 1]}"


# ---------------------------------------------------------------------------
# Chart macros (return raw HTML strings)
# ---------------------------------------------------------------------------
class _Macros:
    """Bundle of macros exposed to the template as `macros.<name>(...)`.

    Returns plain HTML strings (template uses `|safe`). Charts are
    minimalist SVG so WeasyPrint renders them via Cairo without
    extra deps.
    """

    def bar_chart(self, bars: list[MedicationBar]) -> str:
        # Switch to dense mode (no inter-bar gap) when we have too many
        # bars to show 0.6pt of gap between each — otherwise gaps eat the
        # available width and the green vanishes.
        dense = len(bars) > 60
        wrapper_class = "bar-chart dense" if dense else "bar-chart"
        chunks = [f'<div class="{wrapper_class}">']
        for bar in bars:
            cls = {
                "regular": "",
                "late": "late",
                "partial": "partial",
                "skipped": "skipped",
                "not_due": "notdue",
            }.get(bar.status, "")
            chunks.append(f'<span class="bar {cls}"></span>')
        chunks.append("</div>")
        return "".join(chunks)

    def x_axis_dates(self, bars: list[MedicationBar]) -> str:
        n = len(bars)
        if n == 0:
            return ""
        ticks = self._pick_indices(n, max_ticks=min(n, 28))
        labels = []
        for i, bar in enumerate(bars):
            d = bar.due_at
            if i in ticks:
                labels.append(f'<span class="tick">{d.day}\n{d.month}</span>')
            else:
                labels.append('<span class="tick"></span>')
        return f'<div class="x-axis">{"".join(labels)}</div>'

    def monthly_chart(self, monthly: list[MedicationMonthlyAggregate]) -> str:
        if not monthly:
            return ""
        max_h = 26  # pt
        chunks = ['<div class="bar-chart" style="height:%dpt; align-items:flex-end;">' % max_h]
        for m in monthly:
            h = max(2, int((m.rate_pct / 100.0) * max_h))
            chunks.append(
                f'<span class="bar" style="height:{h}pt; flex-grow:1;"></span>'
            )
        chunks.append("</div>")
        return "".join(chunks)

    def x_axis_buckets(self, monthly: list[MedicationMonthlyAggregate]) -> str:
        if not monthly:
            return ""
        labels = []
        for m in monthly:
            label = self._bucket_label(m.bucket)
            labels.append(f'<span class="tick">{label}</span>')
        return f'<div class="x-axis">{"".join(labels)}</div>'

    def sparkline_chart(self, points: list[MedicationSparklinePoint]) -> str:
        if not points:
            return ""
        return self._svg_line(
            xs=list(range(len(points))),
            ys=[p.rate_pct for p in points],
            stroke="#1D9E75",
            y_min=0, y_max=100,
            height_pt=22,
        )

    def x_axis_sparkline(self, points: list[MedicationSparklinePoint]) -> str:
        if not points:
            return ""
        n = len(points)
        ticks = self._pick_indices(n, max_ticks=6)
        labels = []
        for i, p in enumerate(points):
            if i in ticks:
                labels.append(
                    f'<span class="tick">{ITALIAN_MONTHS[p.date.month - 1]}\n{str(p.date.year)[2:]}</span>'
                )
            else:
                labels.append('<span class="tick"></span>')
        return f'<div class="x-axis">{"".join(labels)}</div>'

    def parameter_chart(self, param: dict[str, Any]) -> str:
        points: list[ParameterPoint] = param["points"]
        target_lines: list[dict[str, Any]] = param.get("target_lines") or []
        if not points:
            return '<div class="bar-chart" style="height:22pt;"></div>'
        height = 28
        if param["value_type"] == "numericDouble":
            v1s = [p.v1 for p in points if p.v1 is not None]
            v2s = [p.v2 for p in points if p.v2 is not None]
            all_vals = v1s + v2s
            # Include target line values so the line is in-frame.
            all_vals += [t["value"] for t in target_lines]
            if not all_vals:
                return ""
            y_min = min(all_vals) - 5
            y_max = max(all_vals) + 5
            xs = list(range(len(points)))
            target_svg = "".join(
                self._svg_target(
                    value=t["value"], color=t["color"],
                    y_min=y_min, y_max=y_max, height_pt=height,
                    inline=(idx > 0),
                )
                for idx, t in enumerate(target_lines)
            )
            line1 = self._svg_line(
                xs=xs, ys=[(p.v1 or 0) for p in points],
                stroke="#2B7DD4", y_min=y_min, y_max=y_max, height_pt=height,
                inline=bool(target_svg),
            )
            line2 = self._svg_line(
                xs=xs, ys=[(p.v2 or 0) for p in points],
                stroke="#1D9E75", y_min=y_min, y_max=y_max, height_pt=height,
                inline=True,
            )
            return target_svg + line1 + line2
        else:
            ys = [(p.v1 or 0) for p in points]
            y_min = min(ys) - (max(ys) - min(ys) + 1) * 0.1
            y_max = max(ys) + (max(ys) - min(ys) + 1) * 0.1
            # Include target lines in y-range so they're visible.
            for t in target_lines:
                y_min = min(y_min, t["value"] - 0.05 * abs(t["value"]))
                y_max = max(y_max, t["value"] + 0.05 * abs(t["value"]))
            target_svg = "".join(
                self._svg_target(
                    value=t["value"], color=t["color"],
                    y_min=y_min, y_max=y_max, height_pt=height,
                    inline=(idx > 0),
                )
                for idx, t in enumerate(target_lines)
            )
            line = self._svg_line(
                xs=list(range(len(points))), ys=ys,
                stroke="#1D9E75", y_min=y_min, y_max=y_max, height_pt=height,
                inline=bool(target_svg),
            )
            return target_svg + line

    def _svg_target(
        self, *, value: float, color: str,
        y_min: float, y_max: float,
        height_pt: int, inline: bool = False,
    ) -> str:
        """Horizontal dashed reference line at `value` on the chart's
        y-axis. Used for clinical targets like 140 mmHg or <1.5 mg/dL."""
        if y_max <= y_min:
            return ""
        width = 480
        normY = (value - y_min) / (y_max - y_min)
        sy = height_pt * 4 - normY * (height_pt * 4)
        style = "" if not inline else f"margin-top:-{height_pt}pt;"
        return (
            f'<svg class="row-chart" viewBox="0 0 {width} {height_pt * 4}" '
            f'preserveAspectRatio="none" style="height:{height_pt}pt; {style}">'
            f'<line x1="0" y1="{sy:.1f}" x2="{width}" y2="{sy:.1f}" '
            f'stroke="{color}" stroke-width="1.2" '
            f'stroke-dasharray="3,3" opacity="0.8"/></svg>'
        )

    # ---------- helpers ----------
    def _pick_indices(self, n: int, *, max_ticks: int) -> set[int]:
        if n <= max_ticks:
            return set(range(n))
        step = max(1, n // max_ticks)
        return set(range(0, n, step))

    def _bucket_label(self, key: str) -> str:
        # "2026-04" → "apr\n26"  ;  "2026-W14" → "W14\n26"
        try:
            if "-W" in key:
                year, week = key.split("-W")
                return f"W{week}\n{year[2:]}"
            year, month = key.split("-")
            mi = int(month) - 1
            return f"{ITALIAN_MONTHS[mi]}\n{year[2:]}"
        except (ValueError, IndexError):
            return key

    def _svg_line(
        self, *, xs: list[int], ys: list[float],
        stroke: str, y_min: float, y_max: float,
        height_pt: int, inline: bool = False,
    ) -> str:
        if not xs or y_max <= y_min:
            return ""
        width = 480  # arbitrary view-box, scales via width:100%
        pts = []
        denom = max(1, max(xs))
        for x, y in zip(xs, ys):
            sx = (x / denom) * width
            sy = height_pt * 4 - ((y - y_min) / (y_max - y_min)) * (height_pt * 4)
            pts.append(f"{sx:.1f},{sy:.1f}")
        d = "M " + " L ".join(pts)
        style = "" if not inline else "margin-top:-%dpt;" % height_pt
        return (
            f'<svg class="row-chart" viewBox="0 0 {width} {height_pt * 4}" '
            f'preserveAspectRatio="none" style="height:{height_pt}pt; {style}">'
            f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="1.4" '
            f'stroke-linejoin="round" stroke-linecap="round"/></svg>'
        )
