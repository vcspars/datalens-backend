"""Utilities for rendering dashboard reports to HTML and PDF.

This module is intentionally lightweight and self-contained so it can be used
both by streaming endpoints (for previews) and by PDF download endpoints.
"""

from __future__ import annotations

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
    height: 90vh;
  }

  .cover-title {
    font-size: 28px;
    font-weight: 700;
    margin-bottom: 0.5em;
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

  .chart-placeholder {
    width: 100%;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    background-color: #ffffff;
    padding: 8px;
    margin-top: 0.35em;
  }

  .chart-placeholder svg {
    width: 100%;
    height: 200px;
    display: block;
  }

  .chart-placeholder text {
    font-size: 10px;
    fill: #374151;
  }
"""


def _build_svg_chart(graph_type: str, cfg: Dict[str, Any]) -> str:
  """
  Build a very simple static SVG chart using the graph_config data.

  This is intentionally minimal but gives a real visual for PDFs without
  needing a browser rendering engine.
  """
  data = cfg.get("data") or []
  x_key = cfg.get("xKey") or ""
  y_key = cfg.get("yKey") or ""

  if not isinstance(data, list) or not x_key or not y_key:
    return '<div class="chart-placeholder">No chart data available.</div>'

  # Extract numeric values
  points: list[tuple[str, float]] = []
  for row in data[:20]:
    try:
      label = str(row.get(x_key, ""))
      raw_val = row.get(y_key, 0)
      value = float(raw_val)
      points.append((label, value))
    except Exception:
      continue

  if not points:
    return '<div class="chart-placeholder">No numeric data available for chart.</div>'

  width = 600
  height = 200

  # Pie chart
  if graph_type == "pie":
    total = sum(v for _, v in points) or 1.0
    cx = width / 2
    cy = height / 2
    radius = min(width, height) * 0.35
    svg_parts: list[str] = []
    svg_parts.append('<div class="chart-placeholder">')
    svg_parts.append(f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Pie chart">')

    start_angle = 0.0
    colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#6366f1", "#ec4899"]

    for idx, (label, value) in enumerate(points):
      fraction = value / total
      sweep = fraction * 360.0
      end_angle = start_angle + sweep

      import math

      x1 = cx + radius * math.cos(math.radians(start_angle))
      y1 = cy + radius * math.sin(math.radians(start_angle))
      x2 = cx + radius * math.cos(math.radians(end_angle))
      y2 = cy + radius * math.sin(math.radians(end_angle))
      large_arc = 1 if sweep > 180 else 0
      d = f"M {cx},{cy} L {x1},{y1} A {radius},{radius} 0 {large_arc},1 {x2},{y2} Z"

      color = colors[idx % len(colors)]
      svg_parts.append(f'<path d="{d}" fill="{color}" />')

      # label for some slices
      if idx % max(1, len(points) // 6) == 0:
        mid_angle = start_angle + sweep / 2
        lx = cx + (radius + 18) * math.cos(math.radians(mid_angle))
        ly = cy + (radius + 18) * math.sin(math.radians(mid_angle))
        svg_parts.append(
          f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{label[:12]}</text>'
        )

      start_angle = end_angle

    svg_parts.append("</svg></div>")
    return "".join(svg_parts)

  # Default: simple bar chart
  max_val = max(v for _, v in points) or 1.0
  padding_left = 40
  padding_bottom = 24
  chart_width = width - padding_left - 10
  chart_height = height - padding_bottom - 10
  bar_width = chart_width / max(len(points), 1)

  svg_parts = []
  svg_parts.append('<div class="chart-placeholder">')
  svg_parts.append(f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Bar chart">')

  # Axes
  x_axis_y = 10 + chart_height
  svg_parts.append(
    f'<line x1="{padding_left}" y1="{x_axis_y}" x2="{padding_left + chart_width}" y2="{x_axis_y}" '
    'stroke="#9ca3af" stroke-width="1" />'
  )

  for idx, (label, value) in enumerate(points):
    norm = value / max_val if max_val else 0
    bar_h = norm * chart_height
    x = padding_left + idx * bar_width + bar_width * 0.1
    y = x_axis_y - bar_h
    w = bar_width * 0.8

    svg_parts.append(
      f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{bar_h:.1f}" fill="#3b82f6" />'
    )

    # X labels: show up to ~8 labels to avoid overlap
    step = max(1, len(points) // 8)
    if idx % step == 0:
      svg_parts.append(
        f'<text x="{x + w/2:.1f}" y="{x_axis_y + 12}" text-anchor="middle">{label[:10]}</text>'
      )

  # Y-axis label
  svg_parts.append(f'<text x="4" y="20" text-anchor="start">{y_key}</text>')

  svg_parts.append("</svg></div>")
  return "".join(svg_parts)


def render_report_html(
    full_report_markdown: str,
    items_for_report: List[Dict],
    title: str | None = None,
    author: str | None = None,
    generated_at: str | None = None,
) -> str:
    """Convert markdown + selected items into a single HTML report string."""

    body_html = markdown(
        full_report_markdown or "",
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
                section_parts.append('<div class="table-wrapper">')
                section_parts.append("<table>")
                # header
                section_parts.append("<thead><tr>")
                for col in columns:
                    section_parts.append(f"<th>{col}</th>")
                section_parts.append("</tr></thead>")
                # body
                section_parts.append("<tbody>")
                for row in rows:
                    section_parts.append("<tr>")
                    for col in columns:
                        val = row.get(col, "")
                        section_parts.append(f"<td>{val}</td>")
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
        <div class="cover-title">{title_html}</div>
        <div class="cover-subtitle">Detailed data analysis report</div>
        <div class="cover-meta"><strong>Generated by:</strong> {author_html}</div>
        {"<div class='cover-meta'><strong>Date:</strong> " + generated_html + "</div>" if generated_html else ""}
        <div class="brand">Generated by SPARSLens</div>
      </div>

      <div class="page-break"></div>

      <!-- Table of contents -->
      <div>
        <h2>Table of Contents</h2>
        <ol>
          <li>Selected Items</li>
          <li>Detailed Analysis</li>
          <li>Additional Insights</li>
          <li>Conclusion</li>
        </ol>
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


def render_pdf_from_html(html: str) -> bytes:
    """Render a PDF bytes object from HTML using WeasyPrint."""
    return HTML(string=html).write_pdf()

