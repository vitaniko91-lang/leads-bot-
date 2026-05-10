"use client";

type Props = {
  value: number;
  onChange: (v: number) => void;
  disabled?: boolean;
};

export function TrafficShareSlider({ value, onChange, disabled }: Props) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm text-textMuted">
        <label htmlFor="traffic" className="uppercase-label">Traffic share</label>
        <span className="tabular-nums text-text">{value}%</span>
      </div>
      <input
        id="traffic"
        type="range"
        min={0}
        max={100}
        step={5}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-accent"
      />
    </div>
  );
}
