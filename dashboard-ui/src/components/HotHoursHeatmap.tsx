type Props = {
  matrix: number[][];
  weekdayLabels: string[];
  hourLabels: string[];
};

function bg(value: number, max: number): string {
  if (max === 0) return "bg-surfaceHi";
  const pct = value / max;
  if (pct === 0) return "bg-surfaceHi";
  if (pct < 0.2) return "bg-accent/15";
  if (pct < 0.4) return "bg-accent/30";
  if (pct < 0.6) return "bg-accent/50";
  if (pct < 0.8) return "bg-accent/70";
  return "bg-accent";
}

export function HotHoursHeatmap({ matrix, weekdayLabels, hourLabels }: Props) {
  const max = Math.max(...matrix.flat(), 1);
  return (
    <div className="overflow-x-auto">
      <div className="inline-block min-w-full">
        <div className="flex">
          <div className="w-12" />
          {hourLabels.map((h) => (
            <div
              key={h}
              className="w-7 text-center text-[10px] tabular-nums text-textDim"
            >
              {h}
            </div>
          ))}
        </div>
        {matrix.map((row, di) => (
          <div key={di} className="flex items-center">
            <div className="w-12 text-right text-xs text-textMuted pr-2">
              {weekdayLabels[di]}
            </div>
            {row.map((v, hi) => (
              <div
                key={hi}
                title={`${weekdayLabels[di]} ${hourLabels[hi]}:00 — ${v} leads`}
                className={`mx-px h-7 w-7 rounded-sm ${bg(v, max)}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
