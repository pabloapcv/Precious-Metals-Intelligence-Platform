interface HeaderProps {
  asOf: string
  macroRows: number
  predictions: number
  refreshing: boolean
  pipelineRunning: boolean
  onRefresh: () => void
  onRunPipeline: () => void
}

export function Header({
  refreshing,
  pipelineRunning,
  onRefresh,
  onRunPipeline,
}: HeaderProps) {
  return (
    <header className="top-bar">
      <div className="top-bar-left">
        <span className="top-bar-title">Precious Metals Macro Intelligence Platform</span>
        <span className="top-bar-badge">Institutional</span>
      </div>
      <div className="top-bar-actions">
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={onRefresh}
          disabled={refreshing || pipelineRunning}
        >
          {refreshing ? 'Syncing…' : '↻ Sync'}
        </button>
        <button
          type="button"
          className="btn btn-sm"
          onClick={onRunPipeline}
          disabled={pipelineRunning || refreshing}
        >
          {pipelineRunning ? (
            <>
              <span className="spinner" aria-hidden />
              Pipeline…
            </>
          ) : (
            'Run Pipeline'
          )}
        </button>
        <a className="btn btn-ghost btn-sm" href="/docs" target="_blank" rel="noreferrer">API</a>
      </div>
    </header>
  )
}
