import { useEffect, useMemo, useState } from 'react'
import { horizonLabel } from '../utils'

export interface PipelinePreset {
  id: string
  label: string
  blurb: string
  eta: string
  stages: string[]
  horizons: number[]
  train_scope: string
  walk_forward: boolean
  lookback_days: number
}

export interface PipelineOptionsPayload {
  stages: Array<{ id: string; label: string; weight: number }>
  horizons: Array<{ days: number; label: string }>
  train_scopes: Array<{ id: string; label: string; blurb: string }>
  presets: PipelinePreset[]
}

export interface PipelineRunRequest {
  preset?: string
  stages: string[]
  horizons: number[]
  train_scope: 'all' | 'liquid'
  walk_forward: boolean
}

interface PipelineRunModalProps {
  open: boolean
  running: boolean
  onClose: () => void
  onRun: (payload: PipelineRunRequest) => void
}

const FALLBACK: PipelineOptionsPayload = {
  stages: [
    { id: 'etl', label: 'Market data', weight: 10 },
    { id: 'features', label: 'Features', weight: 12 },
    { id: 'regime', label: 'Regime', weight: 4 },
    { id: 'train', label: 'Models', weight: 58 },
    { id: 'predict', label: 'Predictions', weight: 6 },
    { id: 'history', label: 'History', weight: 6 },
    { id: 'portfolio', label: 'Portfolio', weight: 2 },
    { id: 'paper', label: 'Paper', weight: 2 },
  ],
  horizons: [
    { days: 5, label: '5d' },
    { days: 10, label: '10d' },
    { days: 20, label: '1m' },
    { days: 63, label: '3m' },
    { days: 126, label: '6m' },
  ],
  train_scopes: [
    { id: 'liquid', label: 'Liquid sleeve', blurb: 'Faster — names used for paper/as-of' },
    { id: 'all', label: 'Full scored universe', blurb: 'Every modeled entity' },
  ],
  presets: [
    {
      id: 'quick_prices',
      label: 'Refresh prices',
      blurb: 'Pull market data, rebuild features, refresh the regime. No training.',
      eta: '2–5 min',
      stages: ['etl', 'features', 'regime'],
      horizons: [5, 10, 20, 63, 126],
      train_scope: 'liquid',
      walk_forward: false,
      lookback_days: 730,
    },
    {
      id: 'signals',
      label: 'Rescore signals',
      blurb: 'Score the latest day with existing models and rebuild the portfolio.',
      eta: '1–3 min',
      stages: ['predict', 'portfolio'],
      horizons: [5, 10, 20, 63, 126],
      train_scope: 'all',
      walk_forward: false,
      lookback_days: 730,
    },
    {
      id: 'short_train',
      label: 'Train short horizons',
      blurb: 'Liquid sleeve · 5d / 10d / 1m · skip walk-forward for speed.',
      eta: '10–25 min',
      stages: ['train', 'predict', 'portfolio'],
      horizons: [5, 10, 20],
      train_scope: 'liquid',
      walk_forward: false,
      lookback_days: 730,
    },
    {
      id: 'paper',
      label: 'Rebuild paper books',
      blurb: 'As-of history + paper. Defaults to short horizons.',
      eta: '15–40 min',
      stages: ['history', 'paper'],
      horizons: [5, 10, 20],
      train_scope: 'liquid',
      walk_forward: false,
      lookback_days: 730,
    },
    {
      id: 'full',
      label: 'Full pipeline',
      blurb: 'Everything: prices through models, as-of history, and all paper books.',
      eta: '1–3+ hrs',
      stages: ['etl', 'features', 'regime', 'train', 'predict', 'history', 'portfolio', 'paper'],
      horizons: [5, 10, 20, 63, 126],
      train_scope: 'all',
      walk_forward: true,
      lookback_days: 730,
    },
  ],
}

export function PipelineRunModal({ open, running, onClose, onRun }: PipelineRunModalProps) {
  const [options, setOptions] = useState<PipelineOptionsPayload>(FALLBACK)
  const [presetId, setPresetId] = useState('short_train')
  const [stages, setStages] = useState<string[]>(FALLBACK.presets[2].stages)
  const [horizons, setHorizons] = useState<number[]>([5, 10, 20])
  const [trainScope, setTrainScope] = useState<'all' | 'liquid'>('liquid')
  const [walkForward, setWalkForward] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [loadingOpts, setLoadingOpts] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoadingOpts(true)
    void fetch('/api/v1/pipeline/options')
      .then(async (res) => {
        if (!res.ok) return FALLBACK
        return (await res.json()) as PipelineOptionsPayload
      })
      .then((payload) => {
        if (cancelled) return
        setOptions(payload)
        const preset = payload.presets.find((p) => p.id === 'short_train') ?? payload.presets[0]
        if (preset) applyPreset(preset)
      })
      .catch(() => {
        if (!cancelled) setOptions(FALLBACK)
      })
      .finally(() => {
        if (!cancelled) setLoadingOpts(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const applyPreset = (preset: PipelinePreset) => {
    setPresetId(preset.id)
    setStages([...preset.stages])
    setHorizons([...preset.horizons])
    setTrainScope(preset.train_scope === 'all' ? 'all' : 'liquid')
    setWalkForward(Boolean(preset.walk_forward))
  }

  const nModels = useMemo(() => {
    const entityGuess = trainScope === 'liquid' ? 14 : 60
    return entityGuess * horizons.length
  }, [trainScope, horizons.length])

  const toggleStage = (id: string) => {
    setPresetId('custom')
    setStages((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  }

  const toggleHorizon = (days: number) => {
    setPresetId('custom')
    setHorizons((prev) => {
      if (prev.includes(days)) {
        const next = prev.filter((h) => h !== days)
        return next.length ? next : prev
      }
      return [...prev, days].sort((a, b) => a - b)
    })
  }

  if (!open) return null

  const selectedPreset = options.presets.find((p) => p.id === presetId)

  return (
    <div className="pipeline-modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="pipeline-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pipeline-run-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="pipeline-modal-head">
          <div>
            <h2 id="pipeline-run-title">Run pipeline</h2>
            <p>Pick a short job or customize stages. Full runs still take a long time.</p>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} disabled={running}>
            Close
          </button>
        </div>

        <div className="pipeline-preset-grid">
          {options.presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={`pipeline-preset ${presetId === preset.id ? 'active' : ''}`}
              onClick={() => applyPreset(preset)}
              disabled={running}
            >
              <span className="pipeline-preset-label">{preset.label}</span>
              <span className="pipeline-preset-eta">{preset.eta}</span>
              <span className="pipeline-preset-blurb">{preset.blurb}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          className="pipeline-advanced-toggle"
          onClick={() => setAdvanced((v) => !v)}
        >
          {advanced ? 'Hide custom options' : 'Customize stages & horizons'}
        </button>

        {advanced && (
          <div className="pipeline-advanced">
            <div className="pipeline-field">
              <span className="pipeline-field-label">Stages</span>
              <div className="pipeline-chip-row">
                {options.stages.map((stage) => (
                  <button
                    key={stage.id}
                    type="button"
                    className={`pipeline-chip ${stages.includes(stage.id) ? 'active' : ''}`}
                    onClick={() => toggleStage(stage.id)}
                    disabled={running}
                  >
                    {stage.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="pipeline-field">
              <span className="pipeline-field-label">Horizons</span>
              <div className="pipeline-chip-row">
                {options.horizons.map((h) => (
                  <button
                    key={h.days}
                    type="button"
                    className={`pipeline-chip ${horizons.includes(h.days) ? 'active' : ''}`}
                    onClick={() => toggleHorizon(h.days)}
                    disabled={running}
                  >
                    {h.label || horizonLabel(h.days)}
                  </button>
                ))}
              </div>
            </div>

            <div className="pipeline-field">
              <span className="pipeline-field-label">Universe</span>
              <div className="pipeline-chip-row">
                {options.train_scopes.map((scope) => (
                  <button
                    key={scope.id}
                    type="button"
                    className={`pipeline-chip ${trainScope === scope.id ? 'active' : ''}`}
                    onClick={() => {
                      setPresetId('custom')
                      setTrainScope(scope.id === 'all' ? 'all' : 'liquid')
                    }}
                    disabled={running}
                    title={scope.blurb}
                  >
                    {scope.label}
                  </button>
                ))}
              </div>
            </div>

            <label className="pipeline-check">
              <input
                type="checkbox"
                checked={walkForward}
                onChange={(e) => {
                  setPresetId('custom')
                  setWalkForward(e.target.checked)
                }}
                disabled={running || !stages.includes('train')}
              />
              Walk-forward validation while training (slower, better catalog metrics)
            </label>
          </div>
        )}

        <div className="pipeline-modal-summary">
          <span>
            {selectedPreset && presetId !== 'custom'
              ? selectedPreset.label
              : 'Custom run'}
            {loadingOpts ? ' · loading options…' : ''}
          </span>
          <span className="mono">
            {stages.length} stages · {horizons.map((h) => horizonLabel(h)).join(' · ')} · ~{nModels} model jobs
          </span>
        </div>

        <div className="pipeline-modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={running}>
            Cancel
          </button>
          <button
            type="button"
            className="btn"
            disabled={running || stages.length === 0 || horizons.length === 0}
            onClick={() =>
              onRun({
                preset: presetId === 'custom' ? undefined : presetId,
                stages,
                horizons,
                train_scope: trainScope,
                walk_forward: walkForward,
              })
            }
          >
            {running ? 'Starting…' : 'Start run'}
          </button>
        </div>
      </div>
    </div>
  )
}
