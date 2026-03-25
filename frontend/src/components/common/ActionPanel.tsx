import type { CSSProperties, ReactNode } from "react";

type Props = {
  title?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
};

export function ActionPanel({ title, children, className, style }: Props) {
  return (
    <div className={`module-card action-panel${className ? ` ${className}` : ""}`} style={style}>
      {title ? <h3 className="action-panel-title">{title}</h3> : null}
      {children}
    </div>
  );
}
