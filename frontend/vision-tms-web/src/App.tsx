import { useState } from 'react'
import type { ReactNode } from 'react'
import { Layout } from './components/Layout'
import { useSystemData } from './hooks/useSystemData'
import { BenchConfigView } from './views/BenchConfigView'
import { CameraTestView } from './views/CameraTestView'
import { RunProgramView } from './views/RunProgramView'
import type { AppView } from './types'
import './App.css'

function App() {
  const [activeView, setActiveView] = useState<AppView>('run')
  const [selectedBenchId, setSelectedBenchId] = useState('')
  const system = useSystemData()
  const effectiveBenchId =
    selectedBenchId || system.benchConfig.active_bench_id || system.benchConfig.benches[0]?.id || ''

  const currentView: Record<AppView, ReactNode> = {
    run: (
      <RunProgramView
        isCommandPending={system.isCommandPending}
        benchConfig={system.benchConfig}
        onStart={system.startProgram}
        onStop={system.stopProgram}
        programs={system.programs}
        selectedBenchId={effectiveBenchId}
        setSelectedBenchId={setSelectedBenchId}
        status={system.status}
      />
    ),
    camera: (
      <CameraTestView
        isCommandPending={system.isCommandPending}
        onStartCameraTest={system.startCameraTest}
        onStopCameraTest={system.stopCameraTest}
        settings={system.settings}
        status={system.status}
      />
    ),
    bench: (
      <BenchConfigView
        key={system.isLoading ? 'bench-loading' : 'bench-ready'}
        benchConfig={system.benchConfig}
        cameraFrameSize={system.settings.camera}
        isCommandPending={system.isCommandPending}
        onSave={system.saveBenchConfig}
      />
    ),
  }

  return (
    <Layout
      activeView={activeView}
      error={system.error}
      isLoading={system.isLoading}
      onNavigate={setActiveView}
      settings={system.settings}
      status={system.status}
    >
      {currentView[activeView]}
    </Layout>
  )
}

export default App
