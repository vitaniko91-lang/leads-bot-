import { forwardRef, InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
  hint?: string;
};

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, error, hint, className = "", id, ...rest },
  ref,
) {
  const inputId = id ?? `inp-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="uppercase-label">{label}</label>
      )}
      <input
        ref={ref}
        id={inputId}
        className={[
          "w-full h-10 px-3 rounded-md bg-surfaceHi border border-border text-text text-sm",
          "placeholder:text-textDim transition-colors",
          "focus:border-accent/60 focus:outline-none",
          error ? "border-danger/60" : "",
          className,
        ].join(" ")}
        {...rest}
      />
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-textMuted">{hint}</p>
      ) : null}
    </div>
  );
});
