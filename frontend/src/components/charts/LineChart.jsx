import { useId, useMemo, useState } from "react";
import useWidth, { niceTicks } from "./useWidth.js";

/**
 * Lines with optional confidence bands over x = 1..100 (% contacted).
 * series: [{ id, label, className, points: [{x, y, lo, hi}], band: bool }]
 * marker: x of the current budget. onPick(x): click or Enter sets the budget.
 * Keyboard: focus the chart, Left/Right move the readout (Shift = 10), Enter picks.
 */
export default function LineChart({ series, marker, onPick, yLabel, formatY, formatTip, height = 340, ariaLabel }) {
  const [wrapRef, width] = useWidth();
  const [cursor, setCursor] = useState(null);
  const descId = useId();
  const m = { top: 16, right: 16, bottom: 40, left: width < 480 ? 44 : 56 };
  const w = width - m.left - m.right;
  const h = height - m.top - m.bottom;

  const [ymin, ymax] = useMemo(() => {
    let lo = 0;
    let hi = 0;
    for (const s of series) {
      for (const p of s.points) {
        const vals = [p.y, s.band ? p.lo : null, s.band ? p.hi : null].filter((v) => Number.isFinite(v));
        for (const v of vals) {
          lo = Math.min(lo, v);
          hi = Math.max(hi, v);
        }
      }
    }
    const pad = (hi - lo) * 0.08 || 1;
    return [lo - pad, hi + pad];
  }, [series]);

  const xs = (x) => m.left + ((x - 0) / 100) * w;
  const ys = (y) => m.top + h - ((y - ymin) / (ymax - ymin)) * h;
  const yTicks = niceTicks(ymin, ymax, 5);
  const xTicks = width < 480 ? [0, 25, 50, 75, 100] : [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

  const path = (pts, key = "y") =>
    pts
      .filter((p) => Number.isFinite(p[key]))
      .map((p, i) => `${i ? "L" : "M"}${xs(p.x).toFixed(1)},${ys(p[key]).toFixed(1)}`)
      .join("");
  const area = (pts) => {
    const ok = pts.filter((p) => Number.isFinite(p.lo) && Number.isFinite(p.hi));
    if (!ok.length) return "";
    const top = ok.map((p, i) => `${i ? "L" : "M"}${xs(p.x).toFixed(1)},${ys(p.hi).toFixed(1)}`).join("");
    const bottom = ok
      .slice()
      .reverse()
      .map((p) => `L${xs(p.x).toFixed(1)},${ys(p.lo).toFixed(1)}`)
      .join("");
    return `${top}${bottom}Z`;
  };

  const xFromEvent = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    return Math.min(100, Math.max(1, Math.round(((px - m.left) / w) * 100)));
  };
  const at = cursor ?? marker;
  const onKey = (e) => {
    const step = e.shiftKey ? 10 : 1;
    if (e.key === "ArrowRight" || e.key === "ArrowUp") setCursor(Math.min(100, (at ?? 0) + step));
    else if (e.key === "ArrowLeft" || e.key === "ArrowDown") setCursor(Math.max(1, (at ?? 2) - step));
    else if (e.key === "Home") setCursor(1);
    else if (e.key === "End") setCursor(100);
    else if ((e.key === "Enter" || e.key === " ") && onPick && at) onPick(at);
    else if (e.key === "Escape") setCursor(null);
    else return;
    e.preventDefault();
  };

  const tipX = at != null ? xs(at) : null;
  const tipRows = at != null ? series.map((s) => ({ s, p: s.points.find((p) => p.x === at) })).filter((r) => r.p) : [];

  return (
    <div className="chart" ref={wrapRef}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={ariaLabel}
        aria-describedby={descId}
        tabIndex={0}
        onKeyDown={onKey}
        onMouseMove={(e) => setCursor(xFromEvent(e))}
        onMouseLeave={() => setCursor(null)}
        onBlur={() => setCursor(null)}
        onClick={(e) => onPick && onPick(xFromEvent(e))}
        className={onPick ? "chart-svg pickable" : "chart-svg"}
      >
        <g className="grid">
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={m.left} x2={m.left + w} y1={ys(t)} y2={ys(t)} className={t === 0 ? "zero" : ""} />
              <text x={m.left - 8} y={ys(t)} dy="0.32em" textAnchor="end">
                {formatY ? formatY(t) : t}
              </text>
            </g>
          ))}
          {xTicks.map((t) => (
            <text key={t} x={xs(t)} y={m.top + h + 20} textAnchor="middle">
              {t}%
            </text>
          ))}
          <text x={m.left + w} y={m.top + h + 36} textAnchor="end" className="axis-title">
            share of customers contacted
          </text>
          {yLabel && (
            <text x={m.left} y={m.top - 4} className="axis-title">
              {yLabel}
            </text>
          )}
        </g>
        {series.map((s) =>
          s.band ? <path key={`${s.id}-band`} d={area(s.points)} className={`band ${s.className}`} /> : null,
        )}
        {series.map((s) => (
          <path key={s.id} d={path(s.points)} className={`line ${s.className}`} />
        ))}
        {marker != null && (
          <g className="marker">
            <line x1={xs(marker)} x2={xs(marker)} y1={m.top} y2={m.top + h} />
            <text x={xs(marker)} y={m.top + 12} dx={marker > 85 ? -6 : 6} textAnchor={marker > 85 ? "end" : "start"}>
              {marker}%
            </text>
          </g>
        )}
        {cursor != null && cursor !== marker && (
          <line className="cursor" x1={xs(cursor)} x2={xs(cursor)} y1={m.top} y2={m.top + h} />
        )}
        {tipRows.map(({ s, p }) =>
          Number.isFinite(p.y) ? <circle key={s.id} cx={xs(p.x)} cy={ys(p.y)} r={4} className={`dot ${s.className}`} /> : null,
        )}
      </svg>
      {at != null && tipRows.length > 0 && (
        <div
          className="tooltip"
          role="status"
          aria-live="polite"
          style={{ left: Math.min(Math.max(tipX - 110, 0), width - 230), top: 24 }}
        >
          <p className="tooltip-title">Top {at}% contacted</p>
          {tipRows.map(({ s, p }) => (
            <p key={s.id} className="tooltip-row">
              <span className={`key ${s.className}`} aria-hidden="true" />
              {formatTip ? formatTip(s, p) : `${s.label}: ${p.y}`}
            </p>
          ))}
        </div>
      )}
      <p id={descId} className="sr-only">
        Use the left and right arrow keys to read values at each share contacted. Press Enter to set the budget there.
      </p>
    </div>
  );
}
