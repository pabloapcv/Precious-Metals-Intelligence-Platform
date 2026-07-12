import { useState } from 'react'
import { Header } from './components/Header'
import { StatusBar } from './components/StatusBar'
import { DashboardSkeleton } from './components/Skeleton'
import { useAppData } from './hooks/useAppData'
import { TerminalLayout } from './layout/TerminalLayout'
import { CommandCenter } from './sections/CommandCenter'
import { Explainability } from './sections/Explainability'
import { ModelValidation } from './sections/ModelValidation'
import { PortfolioInstitutional } from './sections/PortfolioInstitutional'
import { ResearchDesk } from './sections/ResearchDesk'
import { RiskSection } from './sections/RiskSection'
import { SignalBook } from './sections/SignalBook'
import type { WorkspaceId } from './types'

export default function App() {
  const [workspace, setWorkspace] = useState<WorkspaceId>('command')
  const {
    dashboard,
    research,
    explain,
    loading,
    refreshing,
    error,
    pipelineRunning,
    toast,
    fetchAll,
    runPipeline,
    dismissToast,
  } = useAppData()

  if (loading && !dashboard) return <DashboardSkeleton />

  if (error && !dashboard) {
    return (
      <div className="error-page">
        <div className="error-card">
          <h1>Platform unavailable</h1>
          <p>{error}</p>
          <p className="error-hint">Start with <code>make dev</code> → <code>http://localhost:8000</code></p>
          <button type="button" className="btn" onClick={() => fetchAll()}>Retry</button>
        </div>
      </div>
    )
  }

  if (!dashboard) return null

  return (
    <>
      <Header
        asOf={dashboard.as_of}
        macroRows={dashboard.data_status.macro_rows}
        predictions={dashboard.data_status.predictions}
        refreshing={refreshing}
        pipelineRunning={pipelineRunning}
        onRefresh={() => fetchAll(true)}
        onRunPipeline={runPipeline}
      />

      {dashboard.data_status.pipeline_needed && (
        <div className="banner global-banner" role="status">
          <span>Data stale — run pipeline to refresh market data and retrain models (~2 min).</span>
          <button type="button" className="btn btn-sm" onClick={runPipeline} disabled={pipelineRunning}>Run pipeline</button>
        </div>
      )}

      {error && <div className="banner error-banner global-banner" role="alert">{error}</div>}

      {toast && (
        <div className={`toast toast-${toast.type}`} role="status">
          <span>{toast.message}</span>
          <button type="button" className="toast-close" onClick={dismissToast} aria-label="Dismiss">×</button>
        </div>
      )}

      {refreshing && <div className="refresh-bar" aria-hidden />}

      <TerminalLayout
        active={workspace}
        onNavigate={setWorkspace}
        asOf={dashboard.as_of}
        refreshing={refreshing}
      >
        <StatusBar dashboard={dashboard} research={research} />

        <div className="workspace-content">
          {workspace === 'command' && <CommandCenter data={dashboard} />}
          {workspace === 'signals' && research && <SignalBook research={research} />}
          {workspace === 'models' && research && <ModelValidation research={research} />}
          {workspace === 'portfolio' && research && <PortfolioInstitutional research={research} />}
          {workspace === 'research' && research && (
            <ResearchDesk dashboard={dashboard} research={research} />
          )}
          {workspace === 'explain' && explain && (
            <Explainability explain={explain} dashboard={dashboard} />
          )}
          {workspace === 'risk' && (
            <div className="workspace">
              <div className="workspace-head compact">
                <h2 className="workspace-title">Risk Monitor</h2>
              </div>
              <RiskSection
                risk={dashboard.risk}
                etfFlows={dashboard.etf_flows}
                centralBanks={dashboard.central_banks}
                agentScores={dashboard.agent_scores}
              />
            </div>
          )}
        </div>
      </TerminalLayout>
    </>
  )
}
