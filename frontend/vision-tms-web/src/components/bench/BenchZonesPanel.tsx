import type { BenchZone } from '../../types'

interface BenchZonesPanelProps {
  zones: BenchZone[]
  selectedZoneIndex: number
  onSelectZone: (index: number) => void
  onRenameZone: (index: number, name: string) => void
  onToggleTwoHands: (index: number, checked: boolean) => void
  onRemoveZone: (index: number) => void
}

export function BenchZonesPanel({
  zones,
  selectedZoneIndex,
  onSelectZone,
  onRenameZone,
  onToggleTwoHands,
  onRemoveZone,
}: BenchZonesPanelProps) {
  return (
    <section className="panel bench-zones-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Bench layout</p>
          <h2>Zones</h2>
        </div>
        {/* Add Zone button removed — use drag-to-create instead */}
      </div>

      <div className="zone-list">
        {zones.map((zone, index) => (
          <div
            className={`zone-row ${selectedZoneIndex === index ? 'is-selected' : ''}`}
            key={`zone-row-${index}`}
          >
            <button type="button" className="zone-select" onClick={() => onSelectZone(index)}>
              {index + 1}
            </button>
            <label className="field zone-name-field">
              <span>Name</span>
              <input value={zone.name} onChange={(event) => onRenameZone(index, event.target.value)} />
            </label>
            <label className="compact-check">
              <input
                type="checkbox"
                checked={zone.two_hands}
                onChange={(event) => onToggleTwoHands(index, event.target.checked)}
              />
              Two hands
            </label>
            <button
              type="button"
              className="danger-button compact-button"
              onClick={() => onRemoveZone(index)}
            >
              Remove
            </button>
          </div>
        ))}
      </div>
    </section>
  )
}
