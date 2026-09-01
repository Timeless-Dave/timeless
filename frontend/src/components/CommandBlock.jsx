export default function CommandBlock({ title, command, description, onAction, actionLabel = 'Run' }) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(command);
    } catch {
      /* ignore */
    }
  };

  return (
    <article className="command-card card">
      <h3>{title}</h3>
      {description ? <p className="card-lead">{description}</p> : null}
      <div className="command-row">
        <code className="command-code">{command}</code>
        <button type="button" className="ghost small-btn" onClick={copy}>
          Copy
        </button>
      </div>
      {onAction ? (
        <button type="button" className="command-action" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </article>
  );
}
