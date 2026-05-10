import { HTMLAttributes } from "react";

type Props = HTMLAttributes<HTMLDivElement> & {
  padded?: boolean;
};

export function Card({ padded = true, className = "", children, ...rest }: Props) {
  return (
    <div
      className={[
        "rounded-lg border border-border bg-surface",
        padded ? "p-5" : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        {subtitle && <p className="text-sm text-textMuted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
