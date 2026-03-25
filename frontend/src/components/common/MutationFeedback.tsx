import { extractErrorMessage } from "../../lib/errorUtils";

type Props = {
  /** The `error` field from a `useMutation` result */
  error?: unknown;
};

/**
 * Renders a styled error message extracted from a mutation error value.
 * Returns null when there is no error.
 */
export function MutationFeedback({ error }: Props) {
  if (error == null) return null;
  return (
    <div className="error-text mutation-error">{extractErrorMessage(error)}</div>
  );
}
