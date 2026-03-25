type Props = { data: unknown; title?: string; maxHeight?: number };

/**
 * Renders a pretty-printed JSON block. Returns null when data is null/undefined.
 */
export function JsonViewer({ data, title, maxHeight = 360 }: Props) {
  if (data == null) return null;
  return (
    <div className="json-viewer">
      {title ? <div className="json-viewer-title">{title}</div> : null}
      <pre className="json-block" style={{ maxHeight }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
