import { useCallback, useEffect, useState } from 'react'
import type { DashboardData, ExplainData, HistoryData, ResearchData } from '../types'

const API_URL = import.meta.env.VITE_API_URL ?? ''

export function useAppData() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null)
  const [research, setResearch] = useState<ResearchData | null>(null)
  const [explain, setExplain] = useState<ExplainData | null>(null)
  const [history, setHistory] = useState<HistoryData | null>(null)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pipelineRunning, setPipelineRunning] = useState(false)
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

      const [dashRes, researchRes, explainRes] = await Promise.all([
        fetch(`${API_URL}/api/v1/dashboard`),
        fetch(`${API_URL}/api/v1/research`),
        fetch(`${API_URL}/api/v1/explain`),
      ])

      if (!dashRes.ok) throw new Error(await parseError(dashRes))
      setDashboard(await dashRes.json())

      if (researchRes.ok) setResearch(await researchRes.json())
      if (explainRes.ok) setExplain(await explainRes.json())

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

  const runPipeline = async () => {
    setPipelineRunning(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/api/v1/pipeline/run`, { method: 'POST' })
      if (!res.ok) throw new Error(await res.text() || 'Pipeline failed')
      await fetchAll(true)
      setToast({ type: 'success', message: 'Pipeline complete — models retrained, signals refreshed.' })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Pipeline failed'
      setError(msg)
      setToast({ type: 'error', message: msg })
    } finally {
      setPipelineRunning(false)
    }
  }

  return {
    dashboard,
    research,
    explain,
    history,
    historyLoading,
    loading,
    refreshing,
    error,
    pipelineRunning,
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
