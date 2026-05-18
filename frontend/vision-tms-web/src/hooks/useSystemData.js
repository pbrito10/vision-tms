import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client'

const emptyStatus = {
  mode: 'idle',
  run_state: 'idle',
  active_program_id: null,
  active_bench_id: null,
  active_bench_name: null,
  message: 'API offline',
  updated_at: null,
  system_checks: [],
}

const emptySettings = {
  system: {
    line_name: '',
    program_name: '',
    part_number: '',
    camera_serial: '',
  },
  camera: {
    index: 0,
    width: 640,
    height: 480,
    flip: false,
  },
  detection: {
    max_num_hands: 2,
    min_detection_confidence: 0.7,
    min_tracking_confidence: 0.7,
  },
  tracking: {
    dwell_time_seconds: 0.5,
    task_timeout_seconds: 30,
    stillness_threshold_px: 5,
    zones: [],
    two_hands_zones: [],
    cycle_zone_order: [],
    start_zone: null,
    exit_zone: '',
  },
}

const emptyBenchConfig = {
  active_bench_id: null,
  benches: [],
}

const emptyProgramState = {
  captured_at: null,
  current_zone: null,
  current_step_index: null,
  completed_steps: [],
  expected_sequence: [],
  cycle_number: 1,
}

export function useSystemData() {
  const [status, setStatus] = useState(emptyStatus)
  const [programs, setPrograms] = useState([])
  const [settings, setSettings] = useState(emptySettings)
  const [benchConfig, setBenchConfig] = useState(emptyBenchConfig)
  const [programState, setProgramState] = useState(emptyProgramState)
  const [isLoading, setIsLoading] = useState(true)
  const [isCommandPending, setIsCommandPending] = useState(false)
  const [error, setError] = useState(null)

  const applyLiveUpdate = useCallback((liveUpdate) => {
    if (liveUpdate.status) {
      setStatus(liveUpdate.status)
    }
    if (liveUpdate.program_state) {
      setProgramState(liveUpdate.program_state)
    }
    setError(null)
    setIsLoading(false)
  }, [])

  const refreshLive = useCallback(async () => {
    const [nextStatus, nextProgramState] = await Promise.all([
      apiClient.getStatus(),
      apiClient.getProgramState(),
    ])
    applyLiveUpdate({
      status: nextStatus,
      program_state: nextProgramState,
    })
  }, [applyLiveUpdate])

  const refresh = useCallback(async () => {
    try {
      const [nextPrograms, nextSettings, nextBenchConfig] = await Promise.all([
        apiClient.getPrograms(),
        apiClient.getSettings(),
        apiClient.getBenchConfig(),
      ])
      setPrograms(nextPrograms)
      setSettings(nextSettings)
      setBenchConfig(nextBenchConfig)
      await refreshLive()
      setError(null)
    } catch (caughtError) {
      setError(caughtError.message)
    } finally {
      setIsLoading(false)
    }
  }, [refreshLive])

  useEffect(() => {
    const initialLoadId = window.setTimeout(refresh, 0)
    return () => {
      window.clearTimeout(initialLoadId)
    }
  }, [refresh])

  useEffect(() => {
    const source = new EventSource(apiClient.eventsUrl())

    source.addEventListener('system', (event) => {
      try {
        applyLiveUpdate(JSON.parse(event.data))
      } catch {
        setError('Live update payload is invalid')
      }
    })

    source.onerror = () => {
      setError('Live updates disconnected. Reconnecting...')
    }

    return () => source.close()
  }, [applyLiveUpdate])

  const runCommand = useCallback(
    async (command) => {
      setIsCommandPending(true)
      try {
        const response = await command()
        if (response?.status) {
          setStatus(response.status)
        }
        await refresh()
      } catch (caughtError) {
        setError(caughtError.message)
      } finally {
        setIsCommandPending(false)
      }
    },
    [refresh],
  )

  return {
    status,
    programs,
    programState,
    settings,
    benchConfig,
    isLoading,
    isCommandPending,
    error,
    refresh,
    startProgram: (benchId) => runCommand(() => apiClient.startProgram(benchId)),
    stopProgram: () => runCommand(apiClient.stopProgram),
    startCameraTest: () => runCommand(apiClient.startCameraTest),
    stopCameraTest: () => runCommand(apiClient.stopCameraTest),
    saveBenchConfig: async (nextBenchConfig) => {
      setIsCommandPending(true)
      try {
        const savedBenchConfig = await apiClient.updateBenchConfig(nextBenchConfig)
        setBenchConfig(savedBenchConfig)
        setError(null)
        await refresh()
        return savedBenchConfig
      } catch (caughtError) {
        setError(caughtError.message)
        throw caughtError
      } finally {
        setIsCommandPending(false)
      }
    },
  }
}
