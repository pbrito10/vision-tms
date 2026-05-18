export function stateLabel(state) {
  return {
    idle: 'IDLE',
    running: 'RUNNING',
    stopping: 'STOPPING',
    error: 'ERROR',
  }[state] ?? 'UNKNOWN'
}

