import { useCallback, useState } from 'react'
import { apiClient } from '../api/client'
import type { BenchConfigResponse, CommandResponse, RuntimeStatus } from '../types'

interface UseSystemCommandsOptions {
  refresh: () => Promise<void>
  setBenchConfig: (benchConfig: BenchConfigResponse) => void
  setError: (message: string | null) => void
  setStatus: (status: RuntimeStatus) => void
}

export function useSystemCommands({ refresh, setBenchConfig, setError, setStatus }: UseSystemCommandsOptions) {
  const [isCommandPending, setIsCommandPending] = useState(false)

  const runCommand = useCallback(
    async (command: () => Promise<CommandResponse>) => {
      setIsCommandPending(true)
      try {
        const response = await command()
        if (response?.status) {
          setStatus(response.status)
        }
        await refresh()
      } catch (caughtError) {
        setError(errorMessage(caughtError))
      } finally {
        setIsCommandPending(false)
      }
    },
    [refresh, setError, setStatus],
  )

  const saveBenchConfig = useCallback(
    async (nextBenchConfig: BenchConfigResponse) => {
      setIsCommandPending(true)
      try {
        const savedBenchConfig = await apiClient.updateBenchConfig(nextBenchConfig)
        setBenchConfig(savedBenchConfig)
        setError(null)
        await refresh()
        return savedBenchConfig
      } catch (caughtError) {
        setError(errorMessage(caughtError))
        throw caughtError
      } finally {
        setIsCommandPending(false)
      }
    },
    [refresh, setBenchConfig, setError],
  )

  return {
    isCommandPending,
    startProgram: (benchId: string) => runCommand(() => apiClient.startProgram(benchId)),
    stopProgram: () => runCommand(apiClient.stopProgram),
    startCameraTest: () => runCommand(apiClient.startCameraTest),
    stopCameraTest: () => runCommand(apiClient.stopCameraTest),
    saveBenchConfig,
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'API command failed'
}
