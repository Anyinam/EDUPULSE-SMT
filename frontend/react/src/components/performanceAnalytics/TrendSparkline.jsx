import React, { useMemo } from 'react';

export function formatTrendDelta(value) {
  if (value === null || value === undefined) return 'Baseline pending';
  return `${value >= 0 ? '+' : ''}${value}%`;
}

function buildSparkline(points, width = 240, height = 72) {
  if (!points?.length) {
    return { path: '', dots: [] };
  }

  const numericValues = points.map((point) => Number(point.average || 0));
  const min = Math.min(...numericValues);
  const max = Math.max(...numericValues);
  const range = max - min || 1;
  const stepX = points.length > 1 ? width / (points.length - 1) : width / 2;

  const dots = points.map((point, index) => ({
    x: points.length > 1 ? index * stepX : width / 2,
    y: height - (((Number(point.average || 0) - min) / range) * (height - 10) + 5),
    label: point.academic_year,
    average: Number(point.average || 0),
  }));

  return {
    path: dots.map((dot, index) => `${index === 0 ? 'M' : 'L'} ${dot.x} ${dot.y}`).join(' '),
    dots,
  };
}

export default function TrendSparkline({ points, label, strokeClass = 'stroke-blue-600', fillClass = 'fill-blue-600' }) {
  const { path, dots } = useMemo(() => buildSparkline(points), [points]);

  if (!points?.length) {
    return (
      <div className="flex h-22 items-center justify-center rounded-lg border border-dashed border-slate-200 bg-slate-50 text-xs text-slate-400">
        No trend data
      </div>
    );
  }

  return (
    <svg viewBox="0 0 240 72" className="h-22 w-full" role="img" aria-label={label}>
      <line x1="0" y1="66" x2="240" y2="66" stroke="#cbd5e1" strokeWidth="1" strokeDasharray="4 4" />
      <path d={path} fill="none" className={strokeClass} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {dots.map((dot) => (
        <g key={`${label}-${dot.label}`}>
          <circle cx={dot.x} cy={dot.y} r="4" className={fillClass} />
          <title>{`${dot.label}: ${dot.average}%`}</title>
        </g>
      ))}
    </svg>
  );
}
