import { useState } from "react";
import useWidth, { niceTicks } from "./useWidth.js";
import { fmt } from "../../format.js";

/**
 * Observed uplift (treated rate minus control rate) per decile of estimated uplift, with
 * 95% bootstrap whiskers and the model's predicted uplift as a tick. Bars are focusable.
 */
export default function DecileBars({ rows, height = 300 }) {
  const [wrapRef, width] = useWidth();
  const [active, setActive] = useState(null);
  const m = { top: 20, right: 12, bottom: 44, left: width < 480 ? 52 : 64 };
  const w = width - m.left - m.right;
  const h = height - m.top - m.bottom;

  const vals = rows.flatMap((r) => [r.observed_uplift, r.lo, r.hi, r.predicted_uplift, 0]).filter(Number.isFinite);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || 0.01;
  const [ymin, ymax] = [lo - pad, hi + pad];
  const ys = (v) => m.top + h - ((v - ymin) / (ymax - ymin)) * h;
  const slot = w / rows.length;
  const bw = Math.min(44, slot * 0.6);
  const ticks = niceTicks(ymin, ymax, 5);
  const current = rows.find((r) => r.decile === active);

  return (
    <div className="chart" ref={wrapRef}>
      <svg width={width} height={height} role="group" aria-label="Observed uplift by decile of estimated uplift" className="chart-svg">
        <g className="grid">
          {ticks.map((t) => (
            <g key={t}>
              <line x1={m.left} x2={m.left + w} y1={ys(t)} y2={ys(t)} className={Math.abs(t) < 1e-12 ? "zero" : ""} />
              <text x={m.left - 8} y={ys(t)} dy="0.32em" textAnchor="end">
                {fmt.pts(t).replace(" pts", "")}
              </text>
            </g>
          ))}
          <text x={m.left} y={m.top - 6} className="axis-title">
            observed uplift, percentage points
          </text>
          <text x={m.left + w} y={m.top + h + 38} textAnchor="end" className="axis-title">
            decile of estimated uplift (1 = highest)
          </text>
        </g>
        {rows.map((r, i) => {
          const cx = m.left + slot * i + slot / 2;
          const v = Number.isFinite(r.observed_uplift) ? r.observed_uplift : 0;
          const y0 = ys(0);
          const y1 = ys(v);
          const label = `Decile ${r.decile}: observed ${fmt.pts(r.observed_uplift)}, 95% band ${fmt.pts(r.lo)} to ${fmt.pts(r.hi)}, predicted ${fmt.pts(r.predicted_uplift)}`;
          return (
            <g
              key={r.decile}
              tabIndex={0}
              role="img"
              aria-label={label}
              className={`bar-group ${active === r.decile ? "active" : ""}`}
              onFocus={() => setActive(r.decile)}
              onBlur={() => setActive(null)}
              onMouseEnter={() => setActive(r.decile)}
              onMouseLeave={() => setActive(null)}
            >
              <rect x={cx - slot / 2} y={m.top} width={slot} height={h} className="hit" />
              <rect x={cx - bw / 2} y={Math.min(y0, y1)} width={bw} height={Math.max(1, Math.abs(y1 - y0))} className={v >= 0 ? "bar pos" : "bar neg"} />
              {Number.isFinite(r.lo) && Number.isFinite(r.hi) && (
                <g className="whisker">
                  <line x1={cx} x2={cx} y1={ys(r.lo)} y2={ys(r.hi)} />
                  <line x1={cx - 6} x2={cx + 6} y1={ys(r.lo)} y2={ys(r.lo)} />
                  <line x1={cx - 6} x2={cx + 6} y1={ys(r.hi)} y2={ys(r.hi)} />
                </g>
              )}
              {Number.isFinite(r.predicted_uplift) && (
                <line className="predicted" x1={cx - bw / 2 - 4} x2={cx + bw / 2 + 4} y1={ys(r.predicted_uplift)} y2={ys(r.predicted_uplift)} />
              )}
              <text x={cx} y={m.top + h + 18} textAnchor="middle" className="tick-label">
                {r.decile}
              </text>
            </g>
          );
        })}
      </svg>
      {current && (
        <div
          className="tooltip"
          role="status"
          aria-live="polite"
          style={{ left: Math.min(Math.max(m.left + slot * (current.decile - 1) - 80, 0), width - 240), top: 8 }}
        >
          <p className="tooltip-title">Decile {current.decile}</p>
          <p className="tooltip-row">Messaged: {fmt.pct2(current.treated_rate)} of {fmt.int(current.nt)}</p>
          <p className="tooltip-row">Not messaged: {fmt.pct2(current.control_rate)} of {fmt.int(current.nc)}</p>
          <p className="tooltip-row">Observed uplift: {fmt.pts(current.observed_uplift)}</p>
          <p className="tooltip-row">95% band: {fmt.pts(current.lo)} to {fmt.pts(current.hi)}</p>
          <p className="tooltip-row">Model predicted: {fmt.pts(current.predicted_uplift)}</p>
        </div>
      )}
    </div>
  );
}
