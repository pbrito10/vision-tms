import { useState } from 'react'
import { useSystemCommands } from './useSystemCommands'
import { useSystemConfiguration } from './useSystemConfiguration'
import { useSystemLiveData } from './useSystemLiveData'

export function useSystemData() {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const liveData = useSystemLiveData({ setError, setIsLoading })
  const configuration = useSystemConfiguration({
    refreshLive: liveData.refreshLive,
    setError,
    setIsLoading,
  })
  const commands = useSystemCommands({
    refresh: configuration.refresh,
    setBenchConfig: configuration.setBenchConfig,
    setError,
    setStatus: liveData.setStatus,
  })

  return {
    status: liveData.status,
    programs: configuration.programs,
    programState: liveData.programState,
    settings: configuration.settings,
    benchConfig: configuration.benchConfig,
    isLoading,
    isCommandPending: commands.isCommandPending,
    error,
    refresh: configuration.refresh,
    startProgram: commands.startProgram,
    stopProgram: commands.stopProgram,
    startCameraTest: commands.startCameraTest,
    stopCameraTest: commands.stopCameraTest,
    saveBenchConfig: commands.saveBenchConfig,
  }
}
