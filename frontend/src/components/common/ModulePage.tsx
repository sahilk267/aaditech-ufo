import type { ReactNode } from "react";

type Props = {
  title: string;
  description: string;
  children?: ReactNode;
  isLoading?: boolean;
  error?: string | null;
};

export function ModulePage({ title, description, children, isLoading, error }: Props) {
  return (
    <section className="module-page">
      <h1>{title}</h1>
      <p>{description}</p>
      {isLoading ? <div className="module-status loading">Loading…</div> : null}
      {!isLoading && error ? <div className="module-status error-text">{error}</div> : null}
      {!isLoading && !error ? children ?? null : null}
    </section>
  );
}
