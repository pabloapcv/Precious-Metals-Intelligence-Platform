import { useState } from 'react'
import { Header } from './components/Header'
import { PipelineRunModal } from './components/PipelineRunModal'
import { PipelineTracker } from './components/PipelineTracker'
import { StatusBar } from './components/StatusBar'
import { DashboardSkeleton } from './components/Skeleton'
import { useAppData } from './hooks/useAppData'
import { TerminalLayout } from './layout/TerminalLayout'
import { AllocationDesk } from './sections/AllocationDesk'
import { CommandCenter } from './sections/CommandCenter'
import { Explainability } from './sections/Explainability'
import { HistoryCharts } from './sections/HistoryCharts'
import { MetalsBook } from './sections/MetalsBook'
import { ModelValidation } from './sections/ModelValidation'
import { PaperBook } from './sections/PaperBook'
import { PortfolioInstitutional } from './sections/PortfolioInstitutional'
import { ResearchDesk } from './sections/ResearchDesk'
import { RiskSection } from './sections/RiskSection'
import { SignalBook } from './sections/SignalBook'
import { StrategyDesk } from './sections/StrategyDesk'
import type { WorkspaceId } from './types'

export default function App() {
  const [workspace, setWorkspace] = useState<WorkspaceId>('command')
  const [pipelineModalOpen, setPipelineModalOpen] = useState(false)
  const {
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
        onOpenPipeline={() => setPipelineModalOpen(true)}
      />

      {dashboard.data_status.pipeline_needed && (
        <div className="banner global-banner" role="status">
          <span>Data stale — run the pipeline to refresh prices and train the metals book.</span>
          <button type="button" className="btn btn-sm" onClick={() => setPipelineModalOpen(true)} disabled={pipelineRunning}>Run pipeline</button>
        </div>
      )}

      <PipelineRunModal
        open={pipelineModalOpen}
        running={pipelineRunning}
        onClose={() => setPipelineModalOpen(false)}
        onRun={(payload) => {
          setPipelineModalOpen(false)
          void runPipeline(payload)
        }}
      />

      <PipelineTracker pipeline={pipeline} />

      {error && pipeline?.status !== 'failed' && <div className="banner error-banner global-banner" role="alert">{error}</div>}

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
          {workspace === 'command' && <CommandCenter data={dashboard} allocation={allocation} />}
          {workspace === 'strategies' && strategies && <StrategyDesk strategies={strategies} />}
          {workspace === 'strategies' && !strategies && (
            <div className="workspace">
              <div className="empty-state"><p>Composing strategy playbooks…</p></div>
            </div>
          )}
          {workspace === 'allocation' && allocation && <AllocationDesk allocation={allocation} />}
          {workspace === 'allocation' && !allocation && (
            <div className="workspace">
              <div className="empty-state">
                <p>Comparing gold with stocks, oil, and copper…</p>
              </div>
            </div>
          )}
          {workspace === 'universe' && universe && <MetalsBook universe={universe} />}
          {workspace === 'universe' && !universe && (
            <div className="workspace">
              <div className="empty-state"><p>Loading the metals book…</p></div>
            </div>
          )}
          {workspace === 'signals' && research && <SignalBook research={research} />}
          {workspace === 'models' && research && <ModelValidation research={research} />}
          {workspace === 'paper' && paper && <PaperBook paper={paper} />}
          {workspace === 'paper' && !paper && (
            <div className="workspace"><div className="empty-state"><p>Marking the paper books…</p></div></div>
          )}
          {workspace === 'portfolio' && research && <PortfolioInstitutional research={research} />}
          {workspace === 'research' && research && (
            <ResearchDesk dashboard={dashboard} research={research} />
          )}
          {workspace === 'history' && history && (
            <HistoryCharts
              history={history}
              loading={historyLoading}
              onReload={(days, horizon) => fetchHistory(days, horizon, false)}
            />
          )}
          {workspace === 'history' && !history && (
            <div className="workspace">
              <div className="empty-state">
                <p>{historyLoading ? 'Building historical outlook series…' : 'History unavailable.'}</p>
                <p className="empty-hint">First load backfills prediction history from trained models.</p>
              </div>
            </div>
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
