import { forwardRef, TextareaHTMLAttributes } from "react";

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, Props>(function Textarea(
  { label, className = "", id, ...rest },
  ref,
) {
  const tid = id ?? `txt-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={tid} className="uppercase-label">{label}</label>
      )}
      <textarea
        ref={ref}
        id={tid}
        rows={4}
        className={[
          "w-full px-3 py-2 rounded-md bg-surfaceHi border border-border text-text text-sm",
          "placeholder:text-textDim focus:border-accent/60 focus:outline-none resize-y",
          className,
        ].join(" ")}
        {...rest}
      />
    </div>
  );
});
