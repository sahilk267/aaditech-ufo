type Status = "ok" | "warn" | "error" | "neutral";

type Props = {
  label: string;
  value: string | number;
  detail?: string;
  status?: Status;
};

/**
 * A small summary card for displaying a single metric with an optional
 * coloured status indicator.
 */
export function StatCard({ label, value, detail, status = "neutral" }: Props) {
  return (
    <div className={`stat-card stat-card--${status}`}>
      <span className="label">{label}</span>
      <strong>{value}</strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}
