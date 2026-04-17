import type { ReactNode } from "react";

type Props = {
  title: string;
  description: string;
  children?: ReactNode;
  actions?: ReactNode;
  isLoading?: boolean;
  error?: string | null;
};

export function ModulePage({ title, description, actions, children, isLoading, error }: Props) {
  return (
    <section className="module-page">
      <div className="module-page-header">
        <div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {actions ? <div className="module-page-actions">{actions}</div> : null}
      </div>
      {isLoading ? <div className="module-status loading">Loading…</div> : null}
      {!isLoading && error ? <div className="module-status error-text">{error}</div> : null}
      {!isLoading && !error ? children ?? null : null}
    </section>
  );
}
