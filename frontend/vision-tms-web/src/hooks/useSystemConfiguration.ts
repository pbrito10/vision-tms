import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { Program } from '../types'
import { emptyBenchConfig, emptySettings } from './systemDefaults'

interface UseSystemConfigurationOptions {
  refreshLive: () => Promise<void>
  setError: (message: string | null) => void
  setIsLoading: (isLoading: boolean) => void
}

export function useSystemConfiguration({
  refreshLive,
  setError,
  setIsLoading,
}: UseSystemConfigurationOptions) {
  const [programs, setPrograms] = useState<Program[]>([])
  const [settings, setSettings] = useState(emptySettings)
  const [benchConfig, setBenchConfig] = useState(emptyBenchConfig)

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
      setError(errorMessage(caughtError))
    } finally {
      setIsLoading(false)
    }
  }, [refreshLive, setError, setIsLoading])

  useEffect(() => {
    const initialLoadId = window.setTimeout(refresh, 0)
    return () => {
      window.clearTimeout(initialLoadId)
    }
  }, [refresh])

  return {
    programs,
    settings,
    benchConfig,
    setBenchConfig,
    refresh,
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Failed to load system configuration'
}
