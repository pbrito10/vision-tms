import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { LiveSnapshot } from '../types'
import { emptyProgramState, emptyStatus } from './systemDefaults'

interface UseSystemLiveDataOptions {
  setError: (message: string | null) => void
  setIsLoading: (isLoading: boolean) => void
}

export function useSystemLiveData({ setError, setIsLoading }: UseSystemLiveDataOptions) {
  const [status, setStatus] = useState(emptyStatus)
  const [programState, setProgramState] = useState(emptyProgramState)

  const applyLiveUpdate = useCallback(
    (liveUpdate: LiveSnapshot) => {
      if (liveUpdate.status) {
        setStatus(liveUpdate.status)
      }
      if (liveUpdate.program_state) {
        setProgramState(liveUpdate.program_state)
      }
      setError(null)
      setIsLoading(false)
    },
    [setError, setIsLoading],
  )

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

  useEffect(() => {
    const source = new EventSource(apiClient.eventsUrl())

    source.addEventListener('system', (event) => {
      try {
        applyLiveUpdate(JSON.parse(event.data) as LiveSnapshot)
      } catch {
        setError('Live update payload is invalid')
      }
    })

    source.onerror = () => {
      setError('Live updates disconnected. Reconnecting...')
    }

    return () => source.close()
  }, [applyLiveUpdate, setError])

  return {
    status,
    setStatus,
    programState,
    refreshLive,
  }
}
