const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request(path, options = {}) {
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
    return null
  }

  return response.json()
}

async function requestBlob(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)

  if (!response.ok) {
    const message = await errorMessage(response)
    throw new Error(message)
  }

  return response.blob()
}

async function errorMessage(response) {
  try {
    const body = await response.json()
    return body.detail ?? `API request failed with ${response.status}`
  } catch {
    return `API request failed with ${response.status}`
  }
}

export const apiClient = {
  getStatus: () => request('/api/system/status'),
  getPrograms: () => request('/api/programs'),
  getProgramState: () => request('/api/program/state'),
  getSettings: () => request('/api/settings'),
  getBenchConfig: () => request('/api/bench-config'),
  startProgram: (benchId, programId = 'industrial-assembly') =>
    request('/api/program/start', {
      method: 'POST',
      body: JSON.stringify({ program_id: programId, bench_id: benchId }),
    }),
  stopProgram: () => request('/api/program/stop', { method: 'POST' }),
  startCameraTest: () => request('/api/camera-test/start', { method: 'POST' }),
  stopCameraTest: () => request('/api/camera-test/stop', { method: 'POST' }),
  cameraStreamUrl: () => `${API_BASE_URL}/api/camera/stream`,
  getCameraSnapshot: () => requestBlob('/api/camera/snapshot'),
  eventsUrl: () => `${API_BASE_URL}/api/events`,
  programStreamUrl: () => `${API_BASE_URL}/api/program/stream`,
  updateBenchConfig: (benchConfig) =>
    request('/api/bench-config', {
      method: 'PUT',
      body: JSON.stringify(benchConfig),
    }),
}
