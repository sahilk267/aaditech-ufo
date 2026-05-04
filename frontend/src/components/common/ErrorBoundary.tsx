import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";

type Props = { children: ReactNode };
type State = { hasError: boolean; error: Error | null; info: string };

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, info: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, info: "" };
  }

  componentDidCatch(_error: Error, info: ErrorInfo) {
    this.setState({ info: info.componentStack ?? "" });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, info: "" });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            padding: "40px 24px",
            maxWidth: 640,
            margin: "60px auto",
            background: "var(--color-surface, #fff)",
            border: "1px solid var(--color-error, #ef4444)",
            borderRadius: 8,
            boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
          }}
        >
          <h2 style={{ color: "var(--color-error, #ef4444)", marginBottom: 12 }}>
            Something went wrong
          </h2>
          <p style={{ marginBottom: 8, color: "#475569" }}>
            An unexpected error occurred in this section of the UI.
          </p>
          {this.state.error && (
            <pre
              style={{
                background: "#fef2f2",
                padding: 12,
                borderRadius: 6,
                fontSize: "0.82em",
                overflow: "auto",
                marginBottom: 16,
                color: "#991b1b",
                whiteSpace: "pre-wrap",
              }}
            >
              {this.state.error.message}
              {this.state.info ? `\n\n${this.state.info}` : ""}
            </pre>
          )}
          <div style={{ display: "flex", gap: 10 }}>
            <button type="button" onClick={this.handleReset}>
              Try again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              style={{ background: "var(--color-surface-raised, #f8fafc)" }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
