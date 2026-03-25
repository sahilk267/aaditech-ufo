/**
 * Extract a human-readable error message from an unknown thrown value.
 * Handles Axios error shapes, plain Error objects, and strings.
 */
export function extractErrorMessage(err: unknown): string {
  if (err == null) return "An unexpected error occurred";

  if (typeof err === "string") return err;

  if (typeof err === "object") {
    // Axios-style: err.response.data.error / .details / .message
    const axErr = err as {
      response?: { data?: { error?: string; message?: string; details?: unknown } };
      message?: string;
    };
    const data = axErr.response?.data;
    if (data) {
      if (data.error) {
        const detail =
          data.details != null
            ? typeof data.details === "string"
              ? `: ${data.details}`
              : `: ${JSON.stringify(data.details)}`
            : "";
        return `${data.error}${detail}`;
      }
      if (data.message) return data.message;
    }
    if (axErr.message) return axErr.message;
  }

  return "An unexpected error occurred";
}
