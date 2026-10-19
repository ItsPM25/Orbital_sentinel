import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  titleId,
  description,
  actions,
  className,
}: {
  title: ReactNode;
  titleId?: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-end justify-between gap-4 border-b px-6 pt-6 pb-4", className)}>
      <div className="min-w-0">
        <h1 id={titleId} className="text-xl font-semibold">
          {title}
        </h1>
        {description && <p className="mt-1 max-w-2xl text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

/** A bordered panel with a small title row. Used instead of floating shadowed cards. */
export function Panel({
  title,
  actions,
  children,
  className,
  bodyClassName,
  id,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  id?: string;
}) {
  return (
    <section id={id} className={cn("rounded-md border bg-card", className)}>
      {(title || actions) && (
        <div className="flex min-h-10 items-center justify-between gap-3 border-b px-4 py-2">
          {title && <h2 className="text-[13px] font-semibold">{title}</h2>}
          {actions}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

const STRIP_COLUMNS = { 3: "sm:grid-cols-3", 4: "sm:grid-cols-4", 5: "sm:grid-cols-5" } as const;

/** One row of key figures separated by rules, e.g. the dashboard summary. */
export function StatStrip({
  items,
  columns = 4,
  className,
}: {
  items: { label: string; value: ReactNode; id?: string }[];
  columns?: keyof typeof STRIP_COLUMNS;
  className?: string;
}) {
  return (
    <dl className={cn("grid grid-cols-2 divide-border rounded-md border bg-card sm:divide-x", STRIP_COLUMNS[columns], className)}>
      {items.map((item) => (
        <div key={item.label} className="px-4 py-3">
          <dt className="text-[13px] text-muted-foreground">{item.label}</dt>
          <dd id={item.id} className="num mt-1 text-xl font-medium">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
