import type { AllocationData, DashboardData } from '../types'
import { AllocationStance } from './AllocationDesk'
import { OverviewSection } from './OverviewSection'

interface CommandCenterProps {
  data: DashboardData
  allocation: AllocationData | null
}

export function CommandCenter({ data, allocation }: CommandCenterProps) {
  return (
    <div className="workspace">
      <div className="workspace-head compact">
        <div>
          <h2 className="workspace-title">Command Center</h2>
          <p className="workspace-sub">Morning intelligence briefing · regime · macro · top picks</p>
        </div>
      </div>
      {allocation && <div style={{ marginBottom: '1.25rem' }}><AllocationStance allocation={allocation} compact /></div>}
      <OverviewSection data={data} />
    </div>
  )
}
