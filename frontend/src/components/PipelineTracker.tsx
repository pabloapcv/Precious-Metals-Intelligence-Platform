import { useEffect, useState } from 'react'
import type { PipelineStatus } from '../types'

const HEADING: Record<PipelineStatus['status'], string> = {
  idle: 'Pipeline',
  running: 'Pipeline running',
  complete: 'Pipeline complete',
  failed: 'Pipeline stopped',
}

const COLLAPSE_KEY = 'pmip.pipelineTracker.collapsed'

function formatElapsed(seconds: number | null | undefined): string | null {
  if (seconds == null || seconds < 0) return null
  if (seconds < 60) return `${Math.round(seconds)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  return `${mins}m ${secs.toString().padStart(2, '0')}s`
}

function stageProgress(stage: PipelineStatus['stages'][number]): string | null {
  const done = stage.done ?? 0
  const total = stage.total ?? 0
  if (total <= 0) return null
  return `${done}/${total}`
}

export function PipelineTracker({ pipeline }: { pipeline: PipelineStatus | null }) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return sessionStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      sessionStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [collapsed])

  if (!pipeline || pipeline.status === 'idle') return null

  const current = pipeline.current
  const log = pipeline.log ?? []
  const train = pipeline.train
  const elapsed = formatElapsed(pipeline.elapsed_seconds)
  const showCount =
    train.total > 0 && (pipeline.status === 'running' || pipeline.status === 'complete')
  const currentLine =
    current?.action && current?.item
      ? `${current.action}: ${current.item}`
      : current?.action || current?.item || pipeline.message
  const currentCount =
    current && current.total > 0
      ? `${current.done}/${current.total}${current.unit ? ` ${current.unit}` : ''}`
      : null

  return (
    <section
      className={`pipeline-tracker tracker-${pipeline.status}${collapsed ? ' is-collapsed' : ''}`}
      aria-live="polite"
    >
      <div className="tracker-head">
        <strong>
          {HEADING[pipeline.status]}
          {pipeline.config?.preset ? ` · ${pipeline.config.preset.replace(/_/g, ' ')}` : ''}
        </strong>
        <span className="tracker-meta">
          {elapsed && <span className="tracker-elapsed">{elapsed}</span>}
          <span className="tracker-percent">{Math.round(pipeline.percent)}%</span>
          <button
            type="button"
            className="tracker-collapse-btn"
            onClick={() => setCollapsed((v) => !v)}
            aria-expanded={!collapsed}
            aria-controls="pipeline-tracker-body"
            title={collapsed ? 'Expand pipeline tracker' : 'Minimize pipeline tracker'}
          >
            {collapsed ? 'Expand' : 'Minimize'}
          </button>
        </span>
      </div>
      <div
        className="tracker-bar"
        role="progressbar"
        aria-valuenow={Math.round(pipeline.percent)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="tracker-bar-fill" style={{ width: `${Math.min(pipeline.percent, 100)}%` }} />
      </div>

      {!collapsed && (
        <div id="pipeline-tracker-body" className="tracker-body">
          {pipeline.status === 'running' && (
            <div className="tracker-now">
              <p className="tracker-message">{currentLine}</p>
              {currentCount && <span className="tracker-now-count">{currentCount}</span>}
            </div>
          )}
          {pipeline.status !== 'running' && <p className="tracker-message">{pipeline.message}</p>}

          <ol className="tracker-stages">
            {pipeline.stages.map((stage) => {
              const progress = stageProgress(stage)
              return (
                <li key={stage.id} className={`tracker-stage stage-${stage.status}`}>
                  <span className="tracker-stage-label">{stage.label}</span>
                  {stage.detail && <span className="tracker-stage-detail">{stage.detail}</span>}
                  {progress && <span className="tracker-stage-count">{progress}</span>}
                </li>
              )
            })}
          </ol>

          {showCount && (
            <p className="tracker-count">
              {train.done.toLocaleString()} of {train.total.toLocaleString()} models
              {train.entity ? ` · ${train.entity} ${train.horizon ?? ''}d` : ''}
            </p>
          )}

          {log.length > 0 && (
            <div className="tracker-log" aria-label="Pipeline activity log">
              <div className="tracker-log-head">Activity</div>
              <ol className="tracker-log-list">
                {[...log].reverse().slice(0, 24).map((entry, index) => (
                  <li key={`${entry.at}-${index}`} className="tracker-log-item">
                    <span className="tracker-log-stage">{entry.stage}</span>
                    <span className="tracker-log-text">{entry.text}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {collapsed && pipeline.status === 'running' && (
        <p className="tracker-message tracker-collapsed-line">{currentLine}</p>
      )}
    </section>
  )
}
