"""
Chart generation for query results.

Heuristics (used when no template chart_hint is provided):
  • date/datetime column  +  numeric column        → line chart
  • category column       +  numeric column        → bar chart
  • category column only                           → count bar chart
  • <2 rows or no numeric columns                  → no chart

Output:
  • Always saves a PNG to <chart_output_dir>/chart_<uuid>.png
  • Returns base64-encoded PNG for API embedding
  • Returns chart_type + the actual x/y columns used
"""

from __future__ import annotations

import base64
import io
import os
import uuid
from datetime import date, datetime
from typing import Optional

from config.settings import get_config
from utils.logging_util import setup_logging

logger = setup_logging("chart")


# ────────────────────────────────────────────────────────────────────────────────
# Detection
# ────────────────────────────────────────────────────────────────────────────────

def _is_datetimey(value, col_name: str) -> bool:
    if isinstance(value, (datetime, date)):
        return True
    n = col_name.lower()
    return any(tok in n for tok in ("date", "day", "time", "month", "year"))


def _is_numeric(value, col_name: str) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    n = col_name.lower()
    return any(tok in n for tok in ("count", "records", "record_count", "size", "rows"))


def _is_categorical(value, col_name: str) -> bool:
    return isinstance(value, str)


def detect_chart(rows: list[dict], cols: list[str]) -> Optional[dict]:
    """Return a chart spec {type, x, y} or None if no chart fits."""
    if not rows or len(rows) < 2:
        return None
    sample = rows[0]

    date_col = next((c for c in cols if _is_datetimey(sample.get(c), c)), None)
    numeric_cols = [c for c in cols if _is_numeric(sample.get(c), c)]
    category_cols = [c for c in cols if _is_categorical(sample.get(c), c)]

    if date_col and numeric_cols:
        return {"type": "line", "x": date_col, "y": numeric_cols[0]}
    if category_cols and numeric_cols:
        return {"type": "bar", "x": category_cols[0], "y": numeric_cols[0]}
    if category_cols:
        return {"type": "count_bar", "x": category_cols[0], "y": None}
    return None


# ────────────────────────────────────────────────────────────────────────────────
# Rendering
# ────────────────────────────────────────────────────────────────────────────────

class ChartGenerator:
    def __init__(self):
        self.cfg = get_config()
        os.makedirs(self.cfg.chart_output_dir, exist_ok=True)

    def generate(self, rows: list[dict], cols: list[str], spec: dict) -> dict:
        """Render the chart described by `spec`. Returns metadata + base64 PNG."""
        # Lazy import so the chart layer doesn't crash imports if matplotlib is missing
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.dates import DateFormatter

        chart_type = spec["type"]
        fig, ax = plt.subplots(figsize=(10, 5))
        title = ""

        if chart_type == "line":
            x_col, y_col = spec["x"], spec["y"]
            # Group by x then average y (in case of duplicate dates from multiple feeds)
            xs, ys = _aggregate_by(rows, x_col, y_col, agg="sum")
            ax.plot(xs, ys, marker="o", linewidth=2)
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            title = f"{y_col} over {x_col}"
            if xs and isinstance(xs[0], (date, datetime)):
                ax.xaxis.set_major_formatter(DateFormatter("%Y-%m-%d"))
                fig.autofmt_xdate(rotation=45)

        elif chart_type == "bar":
            x_col, y_col = spec["x"], spec["y"]
            xs, ys = _aggregate_by(rows, x_col, y_col, agg="sum")
            ax.bar([str(x) for x in xs], ys)
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            title = f"{y_col} by {x_col}"
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

        elif chart_type == "count_bar":
            from collections import Counter
            x_col = spec["x"]
            counts = Counter(str(r.get(x_col, "")) for r in rows)
            keys = list(counts.keys())[:20]
            vals = [counts[k] for k in keys]
            ax.bar(keys, vals)
            ax.set_xlabel(x_col)
            ax.set_ylabel("count")
            title = f"Count by {x_col}"
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

        else:
            plt.close(fig)
            raise ValueError(f"Unknown chart_type: {chart_type!r}")

        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        # Save to disk
        filename = f"chart_{uuid.uuid4().hex[:12]}.png"
        path = os.path.join(self.cfg.chart_output_dir, filename)
        fig.savefig(path, format="png", dpi=80)

        # Also base64 for API response
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=80)
        plt.close(fig)
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("utf-8")

        logger.info({
            "event": "chart_generated",
            "type": chart_type,
            "rows": len(rows),
            "path": path,
        })

        return {
            "chart_type": chart_type,
            "title": title,
            "x_column": spec.get("x"),
            "y_column": spec.get("y"),
            "path": path,
            "png_base64": b64,
        }


# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────

def _aggregate_by(rows, x_col, y_col, agg="sum"):
    """Sort by x_col, aggregate y_col per unique x value.

    Rows where x_col is None or y_col is non-numeric are skipped. This avoids
    `TypeError: '<' not supported between datetime and str` when sorting a
    mixed-None column (Python 3 doesn't compare None with concrete types).
    """
    from collections import OrderedDict
    cleaned: list[tuple] = []
    for r in rows:
        k = r.get(x_col)
        v = r.get(y_col)
        if k is None or v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        cleaned.append((k, v))

    cleaned.sort(key=lambda kv: kv[0])

    buckets: "OrderedDict[object, float]" = OrderedDict()
    for k, v in cleaned:
        buckets[k] = buckets.get(k, 0.0) + v if agg == "sum" else v
    return list(buckets.keys()), list(buckets.values())
