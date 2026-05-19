import type {
  BenchConfigResponse,
  CommandResponse,
  Program,
  ProgramStateResponse,
  RuntimeStatus,
  SettingsResponse,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const message = await errorMessage(response)
    throw new Error(message)
  }

  if (response.status === 204) {
    return null as T
  }

  return response.json() as Promise<T>
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, options)

  if (!response.ok) {
    const message = await errorMessage(response)
    throw new Error(message)
  }

  return response.blob()
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: string }
    return body.detail ?? `API request failed with ${response.status}`
  } catch {
    return `API request failed with ${response.status}`
  }
}

export const apiClient = {
  getStatus: () => request<RuntimeStatus>('/api/system/status'),
  getPrograms: () => request<Program[]>('/api/programs'),
  getProgramState: () => request<ProgramStateResponse>('/api/program/state'),
  getSettings: () => request<SettingsResponse>('/api/settings'),
  getBenchConfig: () => request<BenchConfigResponse>('/api/bench-config'),
  startProgram: (benchId: string, programId = 'industrial-assembly') =>
    request<CommandResponse>('/api/program/start', {
      method: 'POST',
      body: JSON.stringify({ program_id: programId, bench_id: benchId }),
    }),
  stopProgram: () => request<CommandResponse>('/api/program/stop', { method: 'POST' }),
  startCameraTest: () => request<CommandResponse>('/api/camera-test/start', { method: 'POST' }),
  stopCameraTest: () => request<CommandResponse>('/api/camera-test/stop', { method: 'POST' }),
  cameraStreamUrl: () => `${API_BASE_URL}/api/camera/stream`,
  getCameraSnapshot: () => requestBlob('/api/camera/snapshot'),
  eventsUrl: () => `${API_BASE_URL}/api/events`,
  programStreamUrl: () => `${API_BASE_URL}/api/program/stream`,
  updateBenchConfig: (benchConfig: BenchConfigResponse) =>
    request<BenchConfigResponse>('/api/bench-config', {
      method: 'PUT',
      body: JSON.stringify(benchConfig),
    }),
}
