type Status = "ok" | "warn" | "error" | "neutral";

type Props = {
  label: string;
  value: string | number;
  detail?: string;
  status?: Status;
  trend?: "up" | "down" | "flat";
  trendLabel?: string;
};

export function StatCard({ label, value, detail, status = "neutral", trend, trendLabel }: Props) {
  const trendIcon = trend === "up" ? "↑" : trend === "down" ? "↓" : trend === "flat" ? "→" : null;
  const trendColor =
    trend === "up"
      ? "var(--color-ok, #22c55e)"
      : trend === "down"
      ? "var(--color-error, #ef4444)"
      : "var(--color-neutral, #94a3b8)";

  return (
    <div className={`stat-card stat-card--${status}`}>
      <span className="label">{label}</span>
      <strong>
        {value}
        {trendIcon && (
          <span
            style={{ marginLeft: 6, fontSize: "0.82em", color: trendColor }}
            title={trendLabel}
          >
            {trendIcon}
          </span>
        )}
      </strong>
      {detail ? <small>{detail}</small> : null}
    </div>
  );
}
