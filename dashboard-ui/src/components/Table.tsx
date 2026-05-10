"use client";
import { ReactNode } from "react";

export type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  width?: string;
  align?: "left" | "right" | "center";
};

type Props<T> = {
  rows: T[];
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  rowKey: (row: T) => string | number;
};

export function Table<T>({ rows, columns, onRowClick, empty, rowKey }: Props<T>) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-12 text-center text-textMuted">
        {empty ?? "No rows"}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th
                key={c.key}
                style={{ width: c.width }}
                className={[
                  "uppercase-label px-4 py-3 text-left font-semibold",
                  c.align === "right" ? "text-right" : "",
                  c.align === "center" ? "text-center" : "",
                ].join(" ")}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={[
                "border-b border-border last:border-b-0 transition-colors",
                onRowClick ? "cursor-pointer hover:bg-surfaceHi" : "",
              ].join(" ")}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={[
                    "px-4 py-3",
                    c.align === "right" ? "text-right" : "",
                    c.align === "center" ? "text-center" : "",
                  ].join(" ")}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
