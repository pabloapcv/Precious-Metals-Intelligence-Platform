import type { WorkspaceId } from '../types'

const WORKSPACES: { id: WorkspaceId; label: string; code: string }[] = [
  { id: 'command', label: 'Command Center', code: 'CMD' },
  { id: 'signals', label: 'Signal Book', code: 'SIG' },
  { id: 'models', label: 'Model Validation', code: 'MDL' },
  { id: 'portfolio', label: 'Portfolio', code: 'PTF' },
  { id: 'research', label: 'Research Desk', code: 'RSH' },
  { id: 'history', label: 'Historical Outlook', code: 'HST' },
  { id: 'explain', label: 'How It Works', code: 'XPL' },
  { id: 'risk', label: 'Risk Monitor', code: 'RSK' },
]

interface TerminalLayoutProps {
  active: WorkspaceId
  onNavigate: (id: WorkspaceId) => void
  asOf: string
  refreshing: boolean
  children: React.ReactNode
}

export function TerminalLayout({ active, onNavigate, asOf, refreshing, children }: TerminalLayoutProps) {
  return (
    <div className="terminal">
      <aside className="sidebar" aria-label="Workspace navigation">
        <div className="sidebar-brand">
          <div className="brand-mark">PMIP</div>
          <div className="brand-sub">Macro Intelligence</div>
        </div>
        <nav className="sidebar-nav">
          {WORKSPACES.map(({ id, label, code }) => (
            <button
              key={id}
              type="button"
              className={`sidebar-item ${active === id ? 'active' : ''}`}
              onClick={() => onNavigate(id)}
              aria-current={active === id ? 'page' : undefined}
            >
              <span className="sidebar-code">{code}</span>
              <span className="sidebar-label">{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-meta">
            <span className="meta-k">As of</span>
            <span className="meta-v">{asOf}</span>
          </div>
          {refreshing && <span className="live-dot">Syncing</span>}
        </div>
      </aside>
      <div className="terminal-main">
        {children}
      </div>
    </div>
  )
}
