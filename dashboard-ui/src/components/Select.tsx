import { forwardRef, SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  options: { value: string; label: string }[];
};

export const Select = forwardRef<HTMLSelectElement, Props>(function Select(
  { label, options, className = "", id, ...rest },
  ref,
) {
  const sid = id ?? `sel-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={sid} className="uppercase-label">{label}</label>
      )}
      <select
        ref={ref}
        id={sid}
        className={[
          "w-full h-10 px-3 rounded-md bg-surfaceHi border border-border text-text text-sm",
          "focus:border-accent/60 focus:outline-none",
          className,
        ].join(" ")}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
});
