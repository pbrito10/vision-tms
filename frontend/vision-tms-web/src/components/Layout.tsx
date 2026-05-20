import type { ReactNode } from 'react'
import type { AppView, RuntimeStatus, SettingsResponse } from '../types'
import { stateLabel } from '../utils/runtime'

const navItems: Array<{ id: AppView; label: string; icon: string }> = [
  { id: 'run', label: 'Run Program', icon: 'R' },
  { id: 'camera', label: 'Camera Test', icon: 'C' },
  { id: 'bench', label: 'Bench Config', icon: 'B' },
]

interface LayoutProps {
  activeView: AppView
  children: ReactNode
  error: string | null
  isLoading: boolean
  onNavigate: (view: AppView) => void
  settings: SettingsResponse
  status: RuntimeStatus
}

export function Layout({
  activeView,
  children,
  error,
  isLoading,
  onNavigate,
  settings,
  status,
}: LayoutProps) {
  const activeLabel = navItems.find((item) => item.id === activeView)?.label ?? 'Run Program'
  const systemAlerts = status.system_checks.filter((check) => check.status !== 'ok')

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            V
          </div>
          <div>
            <p className="eyebrow">Vision TMS</p>
            <strong>{settings.system.line_name || 'Control System'}</strong>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeView === item.id ? 'is-active' : ''}`}
              type="button"
              onClick={() => onNavigate(item.id)}
            >
              <span className="nav-icon" aria-hidden="true">
                {item.icon}
              </span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-status">
          <span className={`status-dot ${status.run_state}`} aria-hidden="true"></span>
          <div>
            <span>{status.message}</span>
            <strong>{stateLabel(status.run_state)}</strong>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Interface de Controle do Sistema</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="topbar-actions">
            <span className={`run-state ${status.run_state}`}>
              {isLoading ? 'LOADING' : stateLabel(status.run_state)}
            </span>
            <button type="button" className="ghost-button" onClick={() => onNavigate('bench')}>
              Bench Config
            </button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}
        {systemAlerts.length > 0 && (
          <div className="warning-banner">
            {systemAlerts.map((check) => (
              <span key={check.name}>
                {check.name}: {check.value}
              </span>
            ))}
          </div>
        )}
        {children}
      </main>
    </div>
  )
}
