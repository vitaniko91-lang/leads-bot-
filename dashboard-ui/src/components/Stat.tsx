import { Card } from "./Card";

type Trend = "up" | "down" | "flat";

type Props = {
  label: string;
  value: string | number;
  delta?: string;
  trend?: Trend;
  hint?: string;
};

const trendColor: Record<Trend, string> = {
  up: "text-accent",
  down: "text-danger",
  flat: "text-textMuted",
};

export function Stat({ label, value, delta, trend = "flat", hint }: Props) {
  return (
    <Card>
      <div className="uppercase-label">{label}</div>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="text-3xl font-bold tracking-tight tabular-nums">{value}</span>
        {delta && (
          <span className={`text-sm font-medium ${trendColor[trend]}`}>{delta}</span>
        )}
      </div>
      {hint && <div className="mt-2 text-sm text-textMuted">{hint}</div>}
    </Card>
  );
}
