"""Utilities for rendering dashboard reports to HTML and PDF.

This module is intentionally lightweight and self-contained so it can be used
both by streaming endpoints (for previews) and by PDF download endpoints.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

from markdown import markdown
from weasyprint import HTML


BASE_CSS = """
  @page {
    size: A4;
    margin: 20mm 15mm 20mm 15mm;
    @bottom-center {
      content: "Page " counter(page) " of " counter(pages);
      font-size: 10px;
      color: #6b7280;
    }
  }

  body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 13px;
    line-height: 1.5;
    color: #111827;
    margin: 24px;
  }

  h1, h2, h3, h4 {
    color: #111827;
    margin-top: 1.4em;
    margin-bottom: 0.6em;
  }

  h1 { font-size: 24px; }
  h2 { font-size: 20px; }
  h3 { font-size: 16px; }
  h4 { font-size: 14px; }

  .page-break {
    page-break-before: always;
  }

  .report-container {
    max-width: 100%;
  }

  .cover-page {
    display: flex;
    flex-direction: column;
    justify-content: center;
    min-height: 90vh;
    position: relative;
  }

  .cover-page::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: linear-gradient(90deg, #1d4ed8 0%, #3b82f6 50%, #60a5fa 100%);
  }

  .cover-visual {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    margin-bottom: 2em;
  }

  .cover-visual .icon-bar {
    width: 48px;
    height: 4px;
    border-radius: 2px;
    background: #1d4ed8;
  }

  .cover-visual .icon-bar:nth-child(1) { width: 32px; opacity: 0.6; }
  .cover-visual .icon-bar:nth-child(2) { width: 56px; opacity: 0.9; }
  .cover-visual .icon-bar:nth-child(3) { width: 40px; opacity: 0.7; }
  .cover-visual .icon-bar:nth-child(4) { width: 64px; }
  .cover-visual .icon-bar:nth-child(5) { width: 36px; opacity: 0.8; }

  .cover-title {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 0.5em;
    color: #111827;
  }

  .cover-subtitle {
    font-size: 16px;
    color: #4b5563;
    margin-bottom: 1.5em;
  }

  .cover-meta {
    font-size: 13px;
    color: #6b7280;
    margin-bottom: 0.25em;
  }

  .brand {
    margin-top: 2em;
    font-size: 13px;
    font-weight: 600;
    color: #1d4ed8;
  }

  .toc-page {
    padding: 1em 0;
  }

  .toc-page h2 {
    font-size: 22px;
    margin-bottom: 1em;
    padding-bottom: 0.5em;
    border-bottom: 2px solid #1d4ed8;
    color: #111827;
  }

  .toc-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .toc-list li {
    padding: 0.5em 0;
    border-bottom: 1px solid #e5e7eb;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
  }

  .toc-list li:last-child {
    border-bottom: none;
  }

  .toc-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: #eff6ff;
    color: #1d4ed8;
    font-weight: 600;
    font-size: 12px;
    flex-shrink: 0;
  }

  .toc-dots {
    flex: 1;
    border-bottom: 1px dotted #9ca3af;
    margin: 0 4px;
    min-width: 20px;
  }

  .report-body {
    margin-bottom: 2em;
  }

  .items-section-title {
    margin-top: 1.5em;
    margin-bottom: 0.75em;
    font-size: 18px;
    font-weight: 600;
  }

  .item-section {
    margin-bottom: 1.5em;
    page-break-inside: avoid;
  }

  .item-section h3 {
    margin-bottom: 0.4em;
  }

  .item-meta {
    font-size: 11px;
    color: #6b7280;
    margin-bottom: 0.5em;
  }

  .table-wrapper {
    width: 100%;
    overflow-x: auto;
    margin-top: 0.25em;
  }

  table {
    border-collapse: collapse;
    width: 100%;
    font-size: 11px;
  }

  th, td {
    border: 1px solid #e5e7eb;
    padding: 4px 6px;
    white-space: nowrap;
  }

  th {
    background-color: #f3f4f6;
    font-weight: 600;
  }

  .transposed-band {
    margin-bottom: 1em;
  }

  .transposed-band table {
    border-collapse: collapse;
    font-size: 11px;
    width: auto;
  }

  .transposed-band th,
  .transposed-band td {
    border: 1px solid #e5e7eb;
    padding: 4px 6px;
    white-space: normal;
    word-break: break-word;
    max-width: 140px;
  }

  .transposed-band th {
    background-color: #f3f4f6;
    font-weight: 600;
    white-space: nowrap;
    text-align: left;
    max-width: none;
  }

  .transposed-band thead th {
    text-align: center;
    font-size: 10px;
    color: #6b7280;
    background-color: #f9fafb;
    padding: 2px 6px;
  }

  .transposed-band thead th:first-child {
    background-color: transparent;
    border-color: transparent;
  }

  .chart-placeholder {
    width: 100%;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background-color: #ffffff;
    padding: 8px;
    margin-top: 0.35em;
  }

  .chart-placeholder svg {
    display: block;
  }

  .chart-placeholder text {
    font-size: 10px;
    fill: #374151;
  }

  .chart-with-legend {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 16px;
    margin-top: 0.35em;
  }

  .chart-with-legend .chart-svg-wrap {
    flex: 1 1 55%;
    min-width: 280px;
  }

  .chart-with-legend .chart-legend-wrap {
    flex: 1 1 35%;
    min-width: 160px;
    font-size: 11px;
    color: #374151;
  }

  .chart-legend-wrap .legend-title {
    font-weight: 600;
    margin-bottom: 8px;
    font-size: 12px;
  }

  .chart-legend-wrap .legend-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }

  .chart-legend-wrap .legend-swatch {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .chart-legend-wrap .legend-label {
    flex: 1;
    word-break: break-word;
  }

  .chart-legend-wrap .legend-value {
    flex-shrink: 0;
    font-weight: 500;
  }
"""


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_PAGE_USABLE_WIDTH_PX = 680  # A4 (210mm) minus 15mm margins, at 96 DPI
_CHAR_WIDTH_PX = 6.5  # average character width at font-size 11px
_CELL_PADDING_PX = 12  # 6px padding on each side


def _estimate_table_width(columns: List[str], rows: List[Dict[str, Any]]) -> float:
    """Estimate total table width in CSS pixels based on cell content."""
    total = 0.0
    sample = rows[:50]
    for col in columns:
        max_len = len(str(col))
        for row in sample:
            max_len = max(max_len, len(str(row.get(col, ""))))
        total += max_len * _CHAR_WIDTH_PX + _CELL_PADDING_PX
    return total


def _render_transposed_table(columns: List[str], rows: List[Dict[str, Any]]) -> str:
    """Render a wide table in transposed banded layout.

    Headers become the left-most column of each band. Original data rows
    are laid out as columns from left to right. When the page width is
    reached, a new band starts below with the headers repeated.
    """
    if not columns or not rows:
        return ""

    header_texts = [str(c) for c in columns]
    header_col_width = (
        max(len(t) for t in header_texts) * _CHAR_WIDTH_PX + _CELL_PADDING_PX
    )
    header_col_width = min(max(header_col_width, 60), 200)

    sample_vals: List[str] = []
    for row in rows[:30]:
        for col in columns:
            sample_vals.append(str(row.get(col, "")))
    if sample_vals:
        avg_len = sum(len(v) for v in sample_vals) / len(sample_vals)
    else:
        avg_len = 8
    data_col_width = min(max(avg_len * _CHAR_WIDTH_PX + _CELL_PADDING_PX, 60), 140)

    remaining = _PAGE_USABLE_WIDTH_PX - header_col_width
    rows_per_band = max(1, int(remaining / data_col_width))

    parts: List[str] = []
    for band_start in range(0, len(rows), rows_per_band):
        band_rows = rows[band_start : band_start + rows_per_band]
        parts.append('<div class="transposed-band">')
        parts.append("<table>")

        parts.append("<thead><tr>")
        parts.append("<th></th>")
        for i in range(len(band_rows)):
            parts.append(f"<th>{band_start + i + 1}</th>")
        parts.append("</tr></thead>")

        parts.append("<tbody>")
        for col in columns:
            parts.append("<tr>")
            parts.append(f"<th>{_escape_html(str(col))}</th>")
            for row in band_rows:
                val = row.get(col, "")
                parts.append(f"<td>{_escape_html(str(val))}</td>")
            parts.append("</tr>")
        parts.append("</tbody>")

        parts.append("</table>")
        parts.append("</div>")

    return "".join(parts)


def _build_svg_chart(graph_type: str, cfg: Dict[str, Any]) -> str:
  """
  Build a static SVG chart with Y-axis numeric scale and a proper legend
  (right or below) so PDF reports show full labels and values.
  """
  import math

  data = cfg.get("data") or []
  x_key = cfg.get("xKey") or ""
  y_key = cfg.get("yKey") or ""

  if not isinstance(data, list) or not x_key or not y_key:
    return '<div class="chart-placeholder">No chart data available.</div>'

  points: list[tuple[str, float]] = []
  for row in data[:30]:
    try:
      label = str(row.get(x_key, ""))
      raw_val = row.get(y_key, 0)
      value = float(raw_val)
      points.append((label, value))
    except Exception:
      continue

  if not points:
    return '<div class="chart-placeholder">No numeric data available for chart.</div>'

  colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#6366f1", "#ec4899", "#14b8a6", "#f97316"]

  # Pie chart: pie + legend on the right with label and value/%
  if graph_type == "pie":
    total = sum(v for _, v in points) or 1.0
    width = 620
    height = 260
    pie_width = 280
    cx = 140
    cy = height / 2
    radius = min(pie_width, height) * 0.38
    svg_parts: list[str] = []

    legend_rows = []
    start_angle = 0.0
    for idx, (label, value) in enumerate(points):
      fraction = value / total
      pct = 100.0 * fraction
      sweep = fraction * 360.0
      end_angle = start_angle + sweep

      x1 = cx + radius * math.cos(math.radians(start_angle))
      y1 = cy + radius * math.sin(math.radians(start_angle))
      x2 = cx + radius * math.cos(math.radians(end_angle))
      y2 = cy + radius * math.sin(math.radians(end_angle))
      large_arc = 1 if sweep > 180 else 0
      d = f"M {cx},{cy} L {x1},{y1} A {radius},{radius} 0 {large_arc},1 {x2},{y2} Z"
      color = colors[idx % len(colors)]
      svg_parts.append(f'<path d="{d}" fill="{color}" />')
      legend_rows.append((color, _escape_html(label), value, pct))
      start_angle = end_angle

    out = ['<div class="chart-with-legend">']
    out.append('<div class="chart-svg-wrap">')
    out.append(f'<svg viewBox="0 0 {pie_width} {height}" style="max-height: 260px;" role="img" aria-label="Pie chart">')
    out.extend(svg_parts)
    out.append("</svg>")
    out.append("</div>")
    out.append('<div class="chart-legend-wrap">')
    out.append(f'<div class="legend-title">{_escape_html(x_key)}</div>')
    for color, lbl, val, pct in legend_rows:
      out.append(
        f'<div class="legend-row">'
        f'<span class="legend-swatch" style="background-color:{color}"></span>'
        f'<span class="legend-label">{lbl}</span>'
        f'<span class="legend-value">{val:.2f} ({pct:.1f}%)</span>'
        f'</div>'
      )
    out.append("</div></div>")
    return "".join(out)

  # Bar chart: Y-axis with numeric ticks + legend below with full category names
  width = 640
  height = 280
  padding_left = 52
  padding_bottom = 36
  padding_top = 16
  chart_width = width - padding_left - 20
  chart_height = height - padding_bottom - padding_top
  max_val = max(v for _, v in points) or 1.0
  n_bars = len(points)
  bar_width = chart_width / max(n_bars, 1)
  x_axis_y = padding_top + chart_height

  # Y-axis ticks (5 steps: 0 to max)
  num_ticks = 5
  tick_labels = []
  for i in range(num_ticks + 1):
    v = max_val * (i / num_ticks)
    if max_val >= 1e6:
      tick_labels.append(f"{v/1e6:.1f}M")
    elif max_val >= 1e3:
      tick_labels.append(f"{v/1e3:.1f}K")
    else:
      tick_labels.append(f"{v:.0f}")

  svg_parts = []
  svg_parts.append('<div class="chart-with-legend">')
  svg_parts.append('<div class="chart-svg-wrap">')
  svg_parts.append(f'<svg viewBox="0 0 {width} {height}" style="max-height: 280px;" role="img" aria-label="Bar chart">')

  # Y-axis line
  svg_parts.append(
    f'<line x1="{padding_left}" y1="{padding_top}" x2="{padding_left}" y2="{x_axis_y}" '
    'stroke="#9ca3af" stroke-width="1" />'
  )
  # X-axis line
  svg_parts.append(
    f'<line x1="{padding_left}" y1="{x_axis_y}" x2="{padding_left + chart_width}" y2="{x_axis_y}" '
    'stroke="#9ca3af" stroke-width="1" />'
  )

  # Y-axis tick labels (numeric scale)
  for i in range(num_ticks + 1):
    y_val = x_axis_y - (i / num_ticks) * chart_height
    svg_parts.append(
      f'<text x="{padding_left - 6}" y="{y_val + 4}" text-anchor="end" font-size="10" fill="#374151">{tick_labels[num_ticks - i]}</text>'
    )
  # Y-axis title
  svg_parts.append(f'<text x="8" y="{padding_top + chart_height/2}" text-anchor="middle" font-size="10" fill="#6b7280" transform="rotate(-90, 8, {padding_top + chart_height/2})">{_escape_html(y_key)}</text>')

  # Bars
  for idx, (label, value) in enumerate(points):
    norm = value / max_val if max_val else 0
    bar_h = norm * chart_height
    x = padding_left + idx * bar_width + bar_width * 0.08
    y = x_axis_y - bar_h
    w = bar_width * 0.84
    color = colors[idx % len(colors)]
    svg_parts.append(
      f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{max(bar_h, 0):.1f}" fill="{color}" />'
    )

  svg_parts.append("</svg>")
  svg_parts.append("</div>")
  # Legend: full category names and values (below chart in layout terms, but we use right-side legend for consistency)
  svg_parts.append('<div class="chart-legend-wrap">')
  svg_parts.append(f'<div class="legend-title">{_escape_html(x_key)}</div>')
  for idx, (label, value) in enumerate(points):
    color = colors[idx % len(colors)]
    val_str = f"{value:,.2f}" if value != int(value) else f"{int(value):,}"
    svg_parts.append(
      f'<div class="legend-row">'
      f'<span class="legend-swatch" style="background-color:{color}"></span>'
      f'<span class="legend-label">{_escape_html(label)}</span>'
      f'<span class="legend-value">{val_str}</span>'
      f'</div>'
    )
  svg_parts.append("</div></div>")
  return "".join(svg_parts)


# Phrase(s) to remove from generated report text (e.g. LLM closing lines)
_REPORT_STRIP_PHRASES = [
    "if you require further detailed analysis or specific data visualizations, please let me know",
    "if you require further detailed analysis, please let me know",
    "if you need further analysis or visualizations, please let me know",
]


def _strip_unwanted_report_phrases(text: str) -> str:
    """Remove known unwanted closing phrases from report markdown."""
    if not text or not text.strip():
        return text
    out = text
    for phrase in _REPORT_STRIP_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        out = pattern.sub("", out)
    out = re.sub(r"\n\s*\n\s*\n+", "\n\n", out).strip()
    return out if out else text


def render_report_html(
    full_report_markdown: str,
    items_for_report: List[Dict],
    title: str | None = None,
    author: str | None = None,
    generated_at: str | None = None,
) -> str:
    """Convert markdown + selected items into a single HTML report string."""
    report_text = _strip_unwanted_report_phrases(full_report_markdown or "")

    body_html = markdown(
        report_text,
        extensions=["tables", "fenced_code", "toc"],
    )

    items_html_parts: List[str] = []
    for item in items_for_report:
        item_type = item.get("item_type", "")
        name = item.get("name", "")
        created_at = item.get("created_at_str") or ""

        meta_bits: List[str] = []
        if item_type:
            meta_bits.append(item_type.capitalize())
        if created_at:
            meta_bits.append(created_at)
        meta_text = " · ".join(meta_bits)

        section_parts: List[str] = []
        section_parts.append('<div class="item-section">')
        section_parts.append(f"<h3>{name or 'Selected item'}</h3>")
        if meta_text:
            section_parts.append(f'<div class="item-meta">{meta_text}</div>')

        if item_type == "table":
            columns = item.get("table_columns") or []
            rows = item.get("table_data") or []

            if columns:
                est_width = _estimate_table_width(columns, rows)
                if est_width > _PAGE_USABLE_WIDTH_PX:
                    section_parts.append(
                        _render_transposed_table(columns, rows)
                    )
                else:
                    section_parts.append('<div class="table-wrapper">')
                    section_parts.append("<table>")
                    section_parts.append("<thead><tr>")
                    for col in columns:
                        section_parts.append(f"<th>{_escape_html(str(col))}</th>")
                    section_parts.append("</tr></thead>")
                    section_parts.append("<tbody>")
                    for row in rows:
                        section_parts.append("<tr>")
                        for col in columns:
                            val = row.get(col, "")
                            section_parts.append(f"<td>{_escape_html(str(val))}</td>")
                        section_parts.append("</tr>")
                    section_parts.append("</tbody>")
                    section_parts.append("</table>")
                    section_parts.append("</div>")
        elif item_type == "graph":
            graph_type = item.get("graph_type") or ""
            cfg = item.get("graph_config") or {}

            desc_bits: List[str] = []
            if graph_type:
                desc_bits.append(f"Type: {graph_type}")
            x_key = cfg.get("xKey", "")
            y_key = cfg.get("yKey", "")
            if x_key:
                desc_bits.append(f"X-axis: {x_key}")
            if y_key:
                desc_bits.append(f"Y-axis: {y_key}")
            desc = " | ".join(desc_bits) or "Chart preview"

            # Small caption above the chart
            section_parts.append(f'<div class="item-meta">{desc}</div>')
            # Static SVG chart using the same graph_config data
            section_parts.append(_build_svg_chart(graph_type, cfg))

        section_parts.append("</div>")  # .item-section
        items_html_parts.append("".join(section_parts))

    items_block = ""
    if items_html_parts:
        items_block = (
            '<h2 class="items-section-title">Selected Items</h2>'
            + "".join(items_html_parts)
        )

    title_html = title or "DataLens Report"
    author_html = author or "Unknown user"
    generated_html = generated_at or ""

    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{title_html}</title>
    <style>
    {BASE_CSS}
    </style>
  </head>
  <body>
    <div class="report-container">
      <!-- Cover page -->
      <div class="cover-page">
        <div class="cover-visual">
          <span class="icon-bar"></span><span class="icon-bar"></span><span class="icon-bar"></span><span class="icon-bar"></span><span class="icon-bar"></span>
        </div>
        <div class="cover-title">{title_html}</div>
        <div class="cover-subtitle">Detailed data analysis report</div>
        <div class="cover-meta"><strong>Generated by:</strong> {author_html}</div>
        {"<div class='cover-meta'><strong>Date:</strong> " + generated_html + "</div>" if generated_html else ""}
        <div class="brand">Generated by SPARSLens</div>
      </div>

      <div class="page-break"></div>

      <!-- Table of contents -->
      <div class="toc-page">
        <h2>Table of Contents</h2>
        <ul class="toc-list">
          <li><span class="toc-num">1</span> Selected Items<span class="toc-dots"></span></li>
          <li><span class="toc-num">2</span> Detailed Analysis &amp; Findings<span class="toc-dots"></span></li>
          <li><span class="toc-num">3</span> Additional Insights<span class="toc-dots"></span></li>
          <li><span class="toc-num">4</span> Conclusion<span class="toc-dots"></span></li>
        </ul>
      </div>

      <div class="page-break"></div>

      <!-- Selected items -->
      {items_block}

      <div class="page-break"></div>

      <!-- Main analysis body from LLM -->
      <div class="report-body">
        <h2>Detailed Analysis & Findings</h2>
        {body_html}
      </div>
    </div>
  </body>
</html>
"""
    return html


def render_simple_report_html(full_report_markdown: str, title: str | None = None) -> str:
    """
    Render markdown to HTML for a minimal PDF (no cover, no TOC, no extra sections).
    Used for the chat-section Database Analysis Report download; differs from
    dashboard reports which include cover page and table of contents.
    """
    body_html = markdown(
        full_report_markdown or "",
        extensions=["tables", "fenced_code"],
    )
    title_html = title or "Database Analysis Report"
    html = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>{title_html}</title>
    <style>
    {BASE_CSS}
    </style>
  </head>
  <body>
    <div class="report-container">
      <div class="report-body">
        {body_html}
      </div>
    </div>
  </body>
</html>
"""
    return html


def render_pdf_from_html(html: str) -> bytes:
    """Render a PDF bytes object from HTML using WeasyPrint."""
    return HTML(string=html).write_pdf()

