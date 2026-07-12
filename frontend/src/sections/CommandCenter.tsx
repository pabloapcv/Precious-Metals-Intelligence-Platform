import type { DashboardData } from '../types'
import { OverviewSection } from './OverviewSection'

interface CommandCenterProps {
  data: DashboardData
}

export function CommandCenter({ data }: CommandCenterProps) {
  return (
    <div className="workspace">
      <div className="workspace-head compact">
        <div>
          <h2 className="workspace-title">Command Center</h2>
          <p className="workspace-sub">Morning intelligence briefing · regime · macro · top picks</p>
        </div>
      </div>
      <OverviewSection data={data} />
    </div>
  )
}
