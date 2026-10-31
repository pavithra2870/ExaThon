import { useState } from "react";
import { GROUP_COPY, GROUP_ORDER } from "../../dataset.jsx";
import { fmt } from "../../format.js";

/**
 * One horizontal bar split into the four estimated groups. counts: {tipped, anyway, never, put_off}.
 * Every segment has a text label in the legend; segments are focusable for exact numbers.
 */
export default function StackedBar({ counts: raw, caption }) {
  const [active, setActive] = useState(null);
  // Exasol returns exact decimals as strings; coerce so sums add instead of concatenating.
  const counts = Object.fromEntries(GROUP_ORDER.map((g) => [g, Number(raw?.[g] ?? 0) || 0]));
  const total = GROUP_ORDER.reduce((s, g) => s + (counts[g] ?? 0), 0);
  if (!total) return null;
  let acc = 0;

  return (
    <figure className="stacked">
      {caption && <figcaption className="stacked-caption">{caption}</figcaption>}
      <svg className="stacked-svg" viewBox="0 0 1000 36" preserveAspectRatio="none" role="group" aria-label="Estimated groups">
        <defs>
          <pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="8" height="8" className="seg put_off" />
            <line x1="0" y1="0" x2="0" y2="8" className="hatch-line" />
          </pattern>
        </defs>
        {GROUP_ORDER.map((g) => {
          const n = counts[g] ?? 0;
          const x = (acc / total) * 1000;
          const wd = (n / total) * 1000;
          acc += n;
          if (!n) return null;
          return (
            <rect
              key={g}
              x={x}
              y={0}
              width={wd}
              height={36}
              className={`seg ${g} ${active === g ? "active" : ""}`}
              fill={g === "put_off" ? "url(#hatch)" : undefined}
              tabIndex={0}
              role="img"
              aria-label={`${GROUP_COPY[g].label}: ${fmt.int(n)} (${fmt.pct1(n / total)})`}
              onFocus={() => setActive(g)}
              onBlur={() => setActive(null)}
              onMouseEnter={() => setActive(g)}
              onMouseLeave={() => setActive(null)}
            />
          );
        })}
      </svg>
      <ul className="legend">
        {GROUP_ORDER.map((g) => (
          <li key={g} className={active === g ? "active" : ""}>
            <span className={`swatch ${g}`} aria-hidden="true" />
            <span className="legend-label">{GROUP_COPY[g].label}</span>
            <span className="legend-value mono">
              {fmt.pct((counts[g] ?? 0) / total)} · {fmt.int(counts[g] ?? 0)}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
