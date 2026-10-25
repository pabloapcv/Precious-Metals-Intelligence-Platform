import { useCallback, useEffect, useRef, useState } from 'react'
import type { AllocationData, DashboardData, ExplainData, HistoryData, PaperData, PipelineStatus, ResearchData, StrategyData, UniverseData } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? ''

export function useAppData() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [research, setResearch] = useState<ResearchData | null>(null)
  const [explain, setExplain] = useState<ExplainData | null>(null)
  const [history, setHistory] = useState<HistoryData | null>(null)
  const [allocation, setAllocation] = useState<AllocationData | null>(null)
  const [universe, setUniverse] = useState<UniverseData | null>(null)
  const [paper, setPaper] = useState<PaperData | null>(null)
  const [strategies, setStrategies] = useState<StrategyData | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null)
  const wasRunning = useRef(false)
  const pollTimer = useRef<number | null>(null)
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  const fetchHistory = useCallback(async (days = 180, horizon = 10, backfill = true) => {
    setHistoryLoading(true)
    try {
      const res = await fetch(
        `${API_URL}/api/v1/history?days=${days}&horizon=${horizon}&backfill=${backfill}`,
      )
      if (res.ok) setHistory(await res.json())
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  const fetchAll = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) setRefreshing(true)
      else setLoading(true)

      const [dashRes, researchRes, explainRes, allocRes, universeRes, paperRes, strategiesRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/dashboard`),
        fetch(`${API_URL}/api/v1/research`),
        fetch(`${API_URL}/api/v1/explain`),
        fetch(`${API_URL}/api/v1/allocation`),
        fetch(`${API_URL}/api/v1/universe`),
        fetch(`${API_URL}/api/v1/paper`),
        fetch(`${API_URL}/api/v1/strategies`),
      ])

      if (!dashRes.ok) throw new Error(await parseError(dashRes))
      setDashboard(await dashRes.json())

      if (researchRes.ok) setResearch(await researchRes.json())
      if (explainRes.ok) setExplain(await explainRes.json())
      if (allocRes.ok) setAllocation(await allocRes.json())
      if (universeRes.ok) setUniverse(await universeRes.json())
      if (paperRes.ok) setPaper(await paperRes.json())
      if (strategiesRes.ok) setStrategies(await strategiesRes.json())

      // History can take longer on first backfill — load after core data
      await fetchHistory(180, 10, true)

      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load platform data')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [fetchHistory])

  useEffect(() => { fetchAll() }, [fetchAll])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 5000)
    return () => clearTimeout(t)
  }, [toast])

  const readPipeline = useCallback(async () => {
    if (pollTimer.current != null) {
      window.clearTimeout(pollTimer.current)
      pollTimer.current = null
    }
    try {
      const res = await fetch(`${API_URL}/api/v1/pipeline/status`)
      if (!res.ok) return
      const data = (await res.json()) as PipelineStatus
      setPipeline(data)
      const running = data.status === 'running'
      setPipelineRunning(running)
      if (running) {
        wasRunning.current = true
        pollTimer.current = window.setTimeout(() => { void readPipeline() }, 1500)
        return
      }
      if (wasRunning.current && data.status === 'complete') {
        wasRunning.current = false
        await fetchAll(true)
        setToast({ type: 'success', message: 'Pipeline complete — models retrained, signals refreshed.' })
      } else if (wasRunning.current && data.status === 'failed') {
        wasRunning.current = false
        setError(data.error || 'Pipeline failed')
        setToast({ type: 'error', message: data.error || 'Pipeline failed' })
      }
    } catch {
      pollTimer.current = window.setTimeout(() => { void readPipeline() }, 3000)
    }
  }, [fetchAll])

  useEffect(() => {
    void readPipeline()
    return () => {
      if (pollTimer.current != null) window.clearTimeout(pollTimer.current)
    }
  }, [readPipeline])

  const runPipeline = async (payload?: {
    preset?: string
    stages?: string[]
    horizons?: number[]
    train_scope?: 'all' | 'liquid'
    walk_forward?: boolean
  }) => {
    setPipelineRunning(true)
    setError(null)
    wasRunning.current = true
    try {
      const res = await fetch(`${API_URL}/api/v1/pipeline/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload ?? { preset: 'full' }),
      })
      if (!res.ok) throw new Error(await parseError(res))
      setPipeline(await res.json())
      void readPipeline()
    } catch (e) {
      wasRunning.current = false
      setPipelineRunning(false)
      const msg = e instanceof Error ? e.message : 'Pipeline failed'
      setError(msg)
      setToast({ type: 'error', message: msg })
    }
  }

  return {
    dashboard,
    research,
    explain,
    history,
    allocation,
    universe,
    paper,
    strategies,
    historyLoading,
    loading,
    refreshing,
    error,
    pipelineRunning,
    pipeline,
    toast,
    fetchAll,
    fetchHistory,
    runPipeline,
    dismissToast: () => setToast(null),
  }
}

async function parseError(res: Response) {
  let detail = `API error: ${res.status}`
  try {
    const err = await res.json()
    if (err.detail) detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail)
  } catch {
    const text = await res.text()
    if (text) detail = text.slice(0, 200)
  }
  return detail
}
