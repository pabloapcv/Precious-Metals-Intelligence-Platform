interface EmptyWorkspaceProps {
  title: string
  hint?: string
  onOpenPipeline?: () => void
  pipelineLabel?: string
}

/** Shared empty state with optional pipeline CTA (PRD §12.1). */
export function EmptyWorkspace({
  title,
  hint,
  onOpenPipeline,
  pipelineLabel = 'Run pipeline',
}: EmptyWorkspaceProps) {
  return (
    <div className="workspace">
      <div className="empty-state">
        <p>{title}</p>
        {hint ? <p className="empty-hint">{hint}</p> : null}
        {onOpenPipeline ? (
          <button type="button" className="btn btn-sm" onClick={onOpenPipeline} style={{ marginTop: '0.75rem' }}>
            {pipelineLabel}
          </button>
        ) : null}
      </div>
    </div>
  )
}
