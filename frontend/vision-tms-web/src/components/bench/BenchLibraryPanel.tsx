import type { BenchConfig } from '../../types'

interface BenchLibraryPanelProps {
  benches: BenchConfig[]
  selectedBench: BenchConfig
  activeBenchId: string
  onSelectBench: (benchId: string) => void
  onRenameBench: (name: string) => void
  onAddBench: () => void
  onRemoveBench: () => void
  onMarkAsActive: () => void
}

export function BenchLibraryPanel({
  benches,
  selectedBench,
  activeBenchId,
  onSelectBench,
  onRenameBench,
  onAddBench,
  onRemoveBench,
  onMarkAsActive,
}: BenchLibraryPanelProps) {
  const isActiveBench = selectedBench.id === activeBenchId

  return (
    <section className="panel bench-library-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Bench configuration</p>
          <h2>{selectedBench.name}</h2>
        </div>
        <span className="result-pill">{isActiveBench ? 'ACTIVE' : 'SAVED'}</span>
      </div>

      <div className="bench-library-grid">
        <label className="field">
          <span>Bench</span>
          <select value={selectedBench.id} onChange={(event) => onSelectBench(event.target.value)}>
            {benches.map((bench) => (
              <option key={bench.id} value={bench.id}>
                {bench.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Name</span>
          <input value={selectedBench.name} onChange={(event) => onRenameBench(event.target.value)} />
        </label>
        <button type="button" className="secondary-button" onClick={onAddBench}>
          New Bench
        </button>
        <button
          type="button"
          className="secondary-button"
          disabled={isActiveBench}
          onClick={onMarkAsActive}
        >
          Use Bench
        </button>
        <button
          type="button"
          className="danger-button"
          disabled={benches.length <= 1}
          onClick={onRemoveBench}
        >
          Remove
        </button>
      </div>
    </section>
  )
}
