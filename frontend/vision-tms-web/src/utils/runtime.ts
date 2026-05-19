import type { RuntimeState } from '../types'

export function stateLabel(state: RuntimeState | string): string {
  return {
    idle: 'IDLE',
    running: 'RUNNING',
    stopping: 'STOPPING',
    error: 'ERROR',
  }[state] ?? 'UNKNOWN'
}
