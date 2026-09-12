"""Self-contained HTML report for recorded decisions.

Reads recorded runs and a generated batch bundle. Renders exactly what the
records contain: it never recomputes a recommendation or invents a number. If a
field is missing it shows "unavailable" rather than a zero.

No external assets, no network, no JavaScript: charts are inline SVG so the file
opens offline from disk.
"""

from __future__ import annotations

import json
from html import escape
from typing import Any, Sequence

CARBON = "#0b0b0f"
PANEL = "#15151c"
PANEL_2 = "#1d1d26"
EDGE = "#33333f"
TEXT = "#f2f2f5"
MUTED = "#9a9aa8"
ELECTRIC = "#00d6ff"
GREEN = "#00d26a"
AMBER = "#ffb800"
DANGER = "#ff4848"
RED = "#e10600"

SERIES_COLORS = [ELECTRIC, GREEN, AMBER, DANGER, "#b56bff", "#ff8a3d"]

STATUS_COLORS = {
    "RECOMMEND": GREEN,
    "RETAIN_REFERENCE": MUTED,
    "FALLBACK": AMBER,
    "UNAVAILABLE": DANGER,
}


def _svg_chart(
    x: Sequence[float],
    series: dict[str, Sequence[float | None]],
    *,
    title: str,
    y_label: str = "",
    width: int = 900,
    height: int = 220,
    zero_line: bool = False,
) -> str:
    if not x:
        return f'<p class="muted">No trace recorded for {escape(title)}.</p>'
    pad_l, pad_r, pad_t, pad_b = 56, 16, 30, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x_min, x_max = min(x), max(x)
    if x_max <= x_min:
        x_max = x_min + 1.0
    values = [v for s in series.values() for v in s if v is not None]
    if not values:
        return f'<p class="muted">No values for {escape(title)}.</p>'
    y_min, y_max = min(values), max(values)
    if zero_line:
        y_min = min(y_min, 0.0)
        y_max = max(y_max, 0.0)
    if y_max <= y_min:
        y_max = y_min + 1.0
    span = y_max - y_min
    y_min -= span * 0.08
    y_max += span * 0.08

    def px(v: float) -> float:
        return pad_l + (v - x_min) / (x_max - x_min) * plot_w

    def py(v: float) -> float:
        return pad_t + (1.0 - (v - y_min) / (y_max - y_min)) * plot_h

    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="{escape(title)}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{PANEL}"/>',
        f'<text x="{pad_l}" y="18" fill="{TEXT}" font-size="13" font-family="monospace">{escape(title)}</text>',
    ]
    for i in range(5):
        frac = i / 4.0
        y = pad_t + frac * plot_h
        value = y_max - frac * (y_max - y_min)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" y2="{y:.1f}" '
            f'stroke="{EDGE}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{y + 4:.1f}" fill="{MUTED}" font-size="10" '
            f'font-family="monospace" text-anchor="end">{value:.0f}</text>'
        )
    if zero_line and y_min < 0 < y_max:
        y0 = py(0.0)
        parts.append(
            f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{pad_l + plot_w}" y2="{y0:.1f}" '
            f'stroke="{AMBER}" stroke-width="1" stroke-dasharray="4 3"/>'
        )
    legend_x = pad_l + 8
    for index, (name, values_seq) in enumerate(series.items()):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        points = [
            f"{px(xv):.1f},{py(vv):.1f}"
            for xv, vv in zip(x, values_seq)
            if vv is not None
        ]
        if len(points) > 1:
            parts.append(
                f'<polyline fill="none" stroke="{color}" stroke-width="1.8" '
                f'points="{" ".join(points)}"/>'
            )
        parts.append(f'<rect x="{legend_x}" y="8" width="10" height="10" fill="{color}"/>')
        parts.append(
            f'<text x="{legend_x + 14}" y="17" fill="{MUTED}" font-size="10" '
            f'font-family="monospace">{escape(name)}</text>'
        )
        legend_x += 22 + 8 * len(name)
    if y_label:
        parts.append(
            f'<text x="{pad_l}" y="{height - 8}" fill="{MUTED}" font-size="10" '
            f'font-family="monospace">t s · {escape(y_label)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _chips(items: Sequence[tuple[str, str]]) -> str:
    return " ".join(
        f'<span class="chip" style="border-color:{color}">{escape(label)}</span>'
        for label, color in items
    )


def render_run(run: dict[str, Any]) -> str:
    summary = run.get("summary", {})
    decisions = run.get("decisions", [])
    trace = run.get("trace", [])
    label = escape(str(run.get("label", summary.get("run_mode", "run"))))
    mode = escape(str(summary.get("run_mode", "unknown")))

    cards = [
        ("final gap", f"{summary.get('final_gap_m', float('nan')):.2f} m"),
        ("energy spent", f"{(summary.get('ego_energy_spent_j') or 0) / 1e6:.3f} MJ"),
        ("passes", str(summary.get("pass_events", "unavailable"))),
        ("catch-ups", str(summary.get("catch_up_events", "unavailable"))),
        ("contacts", str(summary.get("contacts", "unavailable"))),
        ("decisions", str(summary.get("decisions", "unavailable"))),
    ]
    card_html = "".join(
        f'<div class="card"><div class="k">{escape(k)}</div><div class="v">{escape(v)}</div></div>'
        for k, v in cards
    )

    charts = ""
    if trace:
        times = [row["t"] for row in trace]
        charts += _svg_chart(
            times,
            {
                "gap m": [row["gap"] for row in trace],
            },
            title="Gap (rival − ego): negative means the ego is ahead",
            y_label="gap",
            zero_line=True,
        )
        charts += _svg_chart(
            times,
            {
                "ego m/s": [row["ego_v"] for row in trace],
                "rival m/s": [row["rival_v"] for row in trace],
            },
            title="Speed",
            y_label="m/s",
        )
        charts += _svg_chart(
            times,
            {"deploy kW": [(row["p_k_w"] or 0.0) / 1000.0 for row in trace]},
            title="MGU-K DC deployment (positive = discharge)",
            y_label="kW",
            zero_line=True,
        )
        charts += _svg_chart(
            times,
            {"usable MJ": [(row["energy_j"] or 0.0) / 1e6 for row in trace]},
            title="Usable battery energy",
            y_label="MJ",
        )
        if any(row.get("tyre_temp_k") for row in trace):
            charts += _svg_chart(
                times,
                {"tyre K": [row.get("tyre_temp_k") for row in trace]},
                title="Rear tyre temperature",
                y_label="K",
            )
    else:
        charts = '<p class="muted">No trace recorded for this run.</p>'

    rows = []
    for d in decisions:
        status = d.get("status", "unknown")
        color = STATUS_COLORS.get(status, MUTED)
        belief = d.get("belief") or {}
        strong = belief.get("strong_rival_mass")
        rows.append(
            "<tr>"
            f'<td>{d.get("time_s", 0):.0f}</td>'
            f'<td>{escape(str(d.get("family")))}</td>'
            f'<td style="color:{color}">{escape(status)}</td>'
            f'<td>{d.get("gap_m", float("nan")):.2f}</td>'
            f'<td>{d.get("p_k_dc_w", 0) / 1000.0:.0f}</td>'
            f'<td>{"unavailable" if strong is None else f"{strong:.2f}"}</td>'
            f'<td class="muted">{escape(",".join(d.get("reason_codes", [])))}</td>'
            "</tr>"
        )
    table = (
        '<table><thead><tr><th>t s</th><th>action</th><th>status</th><th>gap m</th>'
        "<th>P kW</th><th>strong mass</th><th>reasons</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )

    return f"""
<section class="run">
  <h2>{label}</h2>
  <div class="chips">{_chips([(mode, ELECTRIC), ("simulated", AMBER), ("synthetic parameters", MUTED)])}</div>
  <div class="cards">{card_html}</div>
  <div class="charts">{charts}</div>
  <h3>Decision timeline</h3>
  {table}
</section>
"""


def render_batch(bundle: dict[str, Any]) -> str:
    blocks = []
    for split, aggregate in bundle.get("aggregate_by_split", {}).items():
        rows = "".join(
            "<tr>"
            f'<td>{escape(a["controller"])}</td>'
            f'<td>{a["completed"]}/{a["episodes"]}</td>'
            f'<td>{a["median_final_gap_m"]}</td>'
            f'<td>{a["mean_energy_spent_j"]}</td>'
            f'<td>{a["total_passes"]}</td>'
            f'<td>{a["total_contacts"]}</td>'
            f'<td>{a["total_catch_ups"]}</td>'
            "</tr>"
            for a in aggregate
        )
        blocks.append(
            f"<h3>Aggregate — {escape(split)} split</h3>"
            "<table><thead><tr><th>controller</th><th>completed</th><th>median gap m</th>"
            "<th>mean energy J</th><th>passes</th><th>contacts</th><th>catch-ups</th>"
            f"</tr></thead><tbody>{rows}</tbody></table>"
        )

    claims = "".join(
        f'<li><b style="color:{GREEN if c["status"] == "supported" else AMBER}">'
        f'[{escape(c["status"])}]</b> {escape(c["claim"])} — '
        f'<span class="muted">{escape(c["evidence"])}</span></li>'
        for c in bundle.get("claim_ledger", [])
    )
    split_claims = "".join(
        f'<li><b style="color:{GREEN if c["status"] == "supported" else AMBER}">'
        f'[{escape(c["status"])}]</b> {escape(c["claim"])} — '
        f'<span class="muted">{escape(c["evidence"])}</span></li>'
        for c in bundle.get("split_claims", [])
    )
    limitations = "".join(
        f"<li>{escape(item)}</li>" for item in bundle.get("limitations", [])
    )
    return f"""
<section class="batch">
  <h2>Frozen batch</h2>
  {''.join(blocks)}
  <h3>Claim ledger</h3>
  <ul class="claims">{claims}{split_claims}</ul>
  <h3>Limitations</h3>
  <ul class="claims">{limitations}</ul>
</section>
"""


def render_page(
    runs: Sequence[dict[str, Any]], bundle: dict[str, Any] | None = None
) -> str:
    run_sections = "".join(render_run(run) for run in runs)
    batch_section = render_batch(bundle) if bundle else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GRID//OPS — recorded decisions</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background:{CARBON}; color:{TEXT}; font-family: ui-sans-serif, system-ui, sans-serif; margin:0; padding:24px; }}
  h1 {{ font-size:22px; letter-spacing:.08em; margin:0 0 4px; }}
  h2 {{ font-size:16px; margin:28px 0 8px; color:{ELECTRIC}; }}
  h3 {{ font-size:13px; margin:20px 0 8px; color:{MUTED}; text-transform:uppercase; letter-spacing:.08em; }}
  .sub {{ color:{MUTED}; font-size:12px; margin-bottom:16px; }}
  section {{ background:{PANEL}; border:1px solid {EDGE}; border-radius:10px; padding:16px 18px; margin-bottom:18px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(120px,1fr)); gap:10px; margin:12px 0; }}
  .card {{ background:{PANEL_2}; border:1px solid {EDGE}; border-radius:8px; padding:10px 12px; }}
  .card .k {{ color:{MUTED}; font-size:10px; text-transform:uppercase; letter-spacing:.08em; }}
  .card .v {{ font-family: ui-monospace, monospace; font-size:18px; margin-top:4px; }}
  .chips {{ margin:8px 0 4px; }}
  .chip {{ border:1px solid {EDGE}; border-radius:999px; padding:2px 10px; font-size:11px; color:{MUTED}; margin-right:6px; }}
  .charts {{ display:grid; grid-template-columns:1fr; gap:10px; }}
  table {{ width:100%; border-collapse:collapse; font-family: ui-monospace, monospace; font-size:12px; }}
  th, td {{ text-align:left; padding:5px 8px; border-bottom:1px solid {EDGE}; }}
  th {{ color:{MUTED}; font-weight:500; font-size:10px; text-transform:uppercase; letter-spacing:.06em; }}
  .muted {{ color:{MUTED}; }}
  .claims {{ font-size:12px; line-height:1.7; padding-left:18px; }}
  .notice {{ border-left:3px solid {AMBER}; padding:8px 12px; background:{PANEL_2}; font-size:12px; color:{MUTED}; margin:12px 0; }}
</style></head>
<body>
  <h1>GRID//OPS</h1>
  <div class="sub">Recorded decisions and frozen experiment results. Values are simulated;
  energy and rival state are model estimates or hidden truth in the simulator, never measured telemetry.</div>
  <div class="notice">This view reads recorded runs. It does not recompute a recommendation,
  and it shows <i>unavailable</i> rather than inventing a value.</div>
  {run_sections}
  {batch_section}
</body></html>
"""


def write_report(
    runs: Sequence[dict[str, Any]],
    bundle: dict[str, Any] | None,
    path: str,
) -> str:
    html = render_page(runs, bundle)
    with open(path, "w") as handle:
        handle.write(html)
    return path


def load_json(path: str) -> dict[str, Any]:
    with open(path) as handle:
        return json.load(handle)
