import { apiClient } from '../api/client'
import { InspectionPreview } from '../components/ui'
import { stateLabel } from '../utils/runtime'

export function RunProgramView({
  benchConfig,
  isCommandPending,
  onStart,
  onStop,
  programState,
  programs,
  selectedBenchId,
  setSelectedBenchId,
  status,
}) {
  const benches = benchConfig.benches ?? []
  const activeProgram = programs[0]
  const selectedBench = benches.find((bench) => bench.id === selectedBenchId) ?? benches[0]
  const isRunning = status.mode === 'program' && status.run_state === 'running'
  const currentTask = isRunning
    ? programState.current_zone ?? 'Waiting for zone'
    : 'Ready'

  return (
    <section className="view-grid run-grid">
      <section className="panel command-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Program control</p>
            <h2>{activeProgram?.name ?? 'Industrial Assembly'}</h2>
          </div>
          <span className={`run-state ${status.run_state}`}>{stateLabel(status.run_state)}</span>
        </div>

        <label className="field">
          <span>Bench</span>
          <select
            value={selectedBench?.id ?? ''}
            onChange={(event) => setSelectedBenchId(event.target.value)}
            disabled={isRunning}
          >
            {benches.map((bench) => (
              <option key={bench.id} value={bench.id}>
                {bench.name}
              </option>
            ))}
          </select>
        </label>

        <div className="current-task">
          <span>Current task</span>
          <strong>{currentTask}</strong>
        </div>

        <div className="control-buttons">
          <button
            type="button"
            className="primary-button"
            disabled={!selectedBench || isRunning || isCommandPending}
            onClick={() => onStart(selectedBench.id)}
          >
            Start
          </button>
          <button
            type="button"
            className="danger-button"
            disabled={!isRunning || isCommandPending}
            onClick={onStop}
          >
            Stop
          </button>
        </div>
      </section>

      <section className="panel program-preview-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Vision output</p>
            <h2>Measurement map</h2>
          </div>
        </div>
        {isRunning ? (
          <div className="camera-stream program-stream">
            <img src={apiClient.programStreamUrl()} alt="Program live stream" />
          </div>
        ) : (
          <InspectionPreview compact />
        )}
      </section>
    </section>
  )
}
