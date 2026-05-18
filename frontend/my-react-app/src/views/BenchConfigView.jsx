import { useState } from 'react'

const FRAME_WIDTH = 640
const FRAME_HEIGHT = 480

export function BenchConfigView({ benchConfig, isCommandPending, onSave }) {
  const initialConfig = normalizeBenchCollection(benchConfig)
  const [draft, setDraft] = useState(initialConfig)
  const [selectedBenchId, setSelectedBenchId] = useState(initialConfig.active_bench_id)
  const [selectedZoneIndex, setSelectedZoneIndex] = useState(0)
  const [sequenceZone, setSequenceZone] = useState(initialConfig.benches[0]?.zones[0]?.name ?? '')
  const [saved, setSaved] = useState(false)
  const [dragState, setDragState] = useState(null)

  const selectedBench = draft.benches.find((bench) => bench.id === selectedBenchId) ?? draft.benches[0]
  const selectedZone = selectedBench?.zones[selectedZoneIndex]
  const zoneNames = selectedBench?.zones.map((zone) => zone.name) ?? []
  const isActiveBench = selectedBench?.id === draft.active_bench_id

  const selectBench = (benchId) => {
    const nextBench = draft.benches.find((bench) => bench.id === benchId) ?? draft.benches[0]
    setSelectedBenchId(nextBench.id)
    setSelectedZoneIndex(0)
    setSequenceZone(nextBench.zones[0]?.name ?? '')
  }

  const updateSelectedBench = (updater) => {
    setDraft((current) => ({
      ...current,
      benches: current.benches.map((bench) =>
        bench.id === selectedBench.id ? updater(bench) : bench,
      ),
    }))
  }

  const renameBench = (name) => {
    updateSelectedBench((bench) => ({ ...bench, name }))
  }

  const addBench = () => {
    const newBench = duplicateBench(selectedBench, draft.benches.length + 1)
    setDraft((current) => ({
      ...current,
      benches: [...current.benches, newBench],
    }))
    setSelectedBenchId(newBench.id)
    setSelectedZoneIndex(0)
    setSequenceZone(newBench.zones[0]?.name ?? '')
  }

  const removeBench = () => {
    if (draft.benches.length <= 1) {
      return
    }

    const remaining = draft.benches.filter((bench) => bench.id !== selectedBench.id)
    const nextSelected = remaining[0]
    setDraft((current) => ({
      ...current,
      active_bench_id:
        current.active_bench_id === selectedBench.id ? nextSelected.id : current.active_bench_id,
      benches: remaining,
    }))
    setSelectedBenchId(nextSelected.id)
    setSelectedZoneIndex(0)
    setSequenceZone(nextSelected.zones[0]?.name ?? '')
  }

  const markAsActiveBench = () => {
    setDraft((current) => ({ ...current, active_bench_id: selectedBench.id }))
  }

  const updateZone = (index, key, value) => {
    updateSelectedBench((bench) => ({
      ...bench,
      zones: bench.zones.map((zone, zoneIndex) =>
        zoneIndex === index ? { ...zone, [key]: value } : zone,
      ),
    }))
  }

  const updateZoneBox = (index, nextBox) => {
    updateSelectedBench((bench) => ({
      ...bench,
      zones: bench.zones.map((zone, zoneIndex) =>
        zoneIndex === index ? { ...zone, ...clampBox(nextBox) } : zone,
      ),
    }))
  }

  const addZone = () => {
    const zone = createZoneModel(selectedBench.zones.length + 1, {
      x: 24,
      y: 24,
      width: 120,
      height: 90,
    })
    updateSelectedBench((bench) => ({
      ...bench,
      zones: [...bench.zones, zone],
      start_zone: bench.start_zone ?? zone.name,
      end_zone: bench.end_zone ?? zone.name,
    }))
    setSequenceZone(zone.name)
    setSelectedZoneIndex(selectedBench.zones.length)
  }

  const createZone = (box) => {
    const zone = createZoneModel(selectedBench.zones.length + 1, clampBox(box))
    updateSelectedBench((bench) => ({
      ...bench,
      zones: [...bench.zones, zone],
      start_zone: bench.start_zone ?? zone.name,
      end_zone: bench.end_zone ?? zone.name,
    }))
    setSequenceZone(zone.name)
    setSelectedZoneIndex(selectedBench.zones.length)
  }

  const removeZone = (index) => {
    const removed = selectedBench.zones[index]
    const nextZones = selectedBench.zones.filter((_, zoneIndex) => zoneIndex !== index)
    const nextNames = nextZones.map((zone) => zone.name)

    updateSelectedBench((bench) => ({
      ...bench,
      zones: nextZones,
      cycle_sequence: bench.cycle_sequence.filter((name) => name !== removed.name),
      start_zone: nextNames.includes(bench.start_zone) ? bench.start_zone : nextNames[0] ?? null,
      end_zone: nextNames.includes(bench.end_zone) ? bench.end_zone : nextNames.at(-1) ?? null,
    }))
    setSelectedZoneIndex(Math.max(0, index - 1))
    setSequenceZone(nextNames[0] ?? '')
  }

  const renameZone = (index, name) => {
    const previousName = selectedBench.zones[index].name
    updateSelectedBench((bench) => ({
      ...bench,
      zones: bench.zones.map((zone, zoneIndex) =>
        zoneIndex === index ? { ...zone, name } : zone,
      ),
      cycle_sequence: bench.cycle_sequence.map((step) => (step === previousName ? name : step)),
      start_zone: bench.start_zone === previousName ? name : bench.start_zone,
      end_zone: bench.end_zone === previousName ? name : bench.end_zone,
    }))
    if (sequenceZone === previousName) {
      setSequenceZone(name)
    }
  }

  const addSequenceStep = () => {
    if (!sequenceZone) {
      return
    }
    updateSelectedBench((bench) => ({
      ...bench,
      cycle_sequence: [...bench.cycle_sequence, sequenceZone],
    }))
  }

  const removeSequenceStep = (index) => {
    updateSelectedBench((bench) => ({
      ...bench,
      cycle_sequence: bench.cycle_sequence.filter((_, stepIndex) => stepIndex !== index),
    }))
  }

  const moveSequenceStep = (index, direction) => {
    const target = index + direction
    if (target < 0 || target >= selectedBench.cycle_sequence.length) {
      return
    }
    updateSelectedBench((bench) => {
      const sequence = [...bench.cycle_sequence]
      const [item] = sequence.splice(index, 1)
      sequence.splice(target, 0, item)
      return { ...bench, cycle_sequence: sequence }
    })
  }

  const save = async () => {
    try {
      const savedConfig = normalizeBenchCollection(await onSave(draft))
      const nextSelected = savedConfig.benches.find((bench) => bench.id === selectedBench.id)
        ?? savedConfig.benches.find((bench) => bench.id === savedConfig.active_bench_id)
        ?? savedConfig.benches[0]
      setDraft(savedConfig)
      setSelectedBenchId(nextSelected.id)
      setSaved(true)
      window.setTimeout(() => setSaved(false), 1800)
    } catch {
      setSaved(false)
    }
  }

  const startDrawing = (event) => {
    if (event.target !== event.currentTarget) {
      return
    }
    const point = eventToFramePoint(event)
    setDragState({
      mode: 'create',
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
    })
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const startMoving = (event, index) => {
    event.stopPropagation()
    setSelectedZoneIndex(index)
    const point = eventToFramePoint(event)
    const zone = selectedBench.zones[index]
    setDragState({
      mode: 'move',
      index,
      startX: point.x,
      startY: point.y,
      original: { x: zone.x, y: zone.y, width: zone.width, height: zone.height },
    })
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const startResizing = (event, index) => {
    event.stopPropagation()
    setSelectedZoneIndex(index)
    const point = eventToFramePoint(event)
    const zone = selectedBench.zones[index]
    setDragState({
      mode: 'resize',
      index,
      startX: point.x,
      startY: point.y,
      original: { x: zone.x, y: zone.y, width: zone.width, height: zone.height },
    })
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const updateDrag = (event) => {
    if (!dragState) {
      return
    }

    const point = eventToFramePoint(event)

    if (dragState.mode === 'create') {
      setDragState((current) => ({
        ...current,
        currentX: point.x,
        currentY: point.y,
      }))
      return
    }

    if (dragState.mode === 'move') {
      const dx = point.x - dragState.startX
      const dy = point.y - dragState.startY
      updateZoneBox(dragState.index, {
        ...dragState.original,
        x: dragState.original.x + dx,
        y: dragState.original.y + dy,
      })
      return
    }

    if (dragState.mode === 'resize') {
      const dx = point.x - dragState.startX
      const dy = point.y - dragState.startY
      updateZoneBox(dragState.index, {
        ...dragState.original,
        width: dragState.original.width + dx,
        height: dragState.original.height + dy,
      })
    }
  }

  const finishDrag = (event) => {
    if (!dragState) {
      return
    }

    if (dragState.mode === 'create') {
      const box = boxFromPoints(
        dragState.startX,
        dragState.startY,
        dragState.currentX,
        dragState.currentY,
      )
      if (box.width >= 12 && box.height >= 12) {
        createZone(box)
      }
    }

    setDragState(null)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  const creationBox = dragState?.mode === 'create'
    ? boxFromPoints(dragState.startX, dragState.startY, dragState.currentX, dragState.currentY)
    : null

  return (
    <section className="view-grid bench-grid">
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
            <select value={selectedBench.id} onChange={(event) => selectBench(event.target.value)}>
              {draft.benches.map((bench) => (
                <option key={bench.id} value={bench.id}>
                  {bench.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Name</span>
            <input value={selectedBench.name} onChange={(event) => renameBench(event.target.value)} />
          </label>
          <button type="button" className="secondary-button" onClick={addBench}>
            New Bench
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={isActiveBench}
            onClick={markAsActiveBench}
          >
            Use Bench
          </button>
          <button
            type="button"
            className="danger-button"
            disabled={draft.benches.length <= 1}
            onClick={removeBench}
          >
            Remove
          </button>
        </div>
      </section>

      <section className="panel bench-zones-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Bench layout</p>
            <h2>Zones</h2>
          </div>
          <button type="button" className="secondary-button" onClick={addZone}>
            Add Zone
          </button>
        </div>

        <div className="zone-list">
          {selectedBench.zones.map((zone, index) => (
            <div className={`zone-row ${selectedZoneIndex === index ? 'is-selected' : ''}`} key={`${zone.name}-${index}`}>
              <button type="button" className="zone-select" onClick={() => setSelectedZoneIndex(index)}>
                {index + 1}
              </button>
              <label className="field zone-name-field">
                <span>Name</span>
                <input value={zone.name} onChange={(event) => renameZone(index, event.target.value)} />
              </label>
              <label className="compact-check">
                <input
                  type="checkbox"
                  checked={zone.two_hands}
                  onChange={(event) => updateZone(index, 'two_hands', event.target.checked)}
                />
                Two hands
              </label>
              <button type="button" className="danger-button compact-button" onClick={() => removeZone(index)}>
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>

      <section className="panel bench-preview-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Preview</p>
            <h2>{selectedZone?.name ?? 'Draw a zone'}</h2>
          </div>
          <span className="result-pill">{selectedBench.zones.length} ZONES</span>
        </div>
        <div
          className="bench-preview"
          onPointerDown={startDrawing}
          onPointerMove={updateDrag}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          {selectedBench.zones.map((zone, index) => (
            <button
              type="button"
              className={`bench-zone ${selectedZoneIndex === index ? 'is-selected' : ''}`}
              key={`${zone.name}-preview-${index}`}
              style={boxStyle(zone)}
              onPointerDown={(event) => startMoving(event, index)}
            >
              {zone.name}
              <span
                className="resize-handle"
                onPointerDown={(event) => startResizing(event, index)}
              ></span>
            </button>
          ))}
          {creationBox && <div className="bench-zone draft-zone" style={boxStyle(creationBox)}></div>}
        </div>
      </section>

      <section className="panel bench-cycle-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Cycle logic</p>
            <h2>Start, end and sequence</h2>
          </div>
        </div>

        <div className="form-grid sequence-controls">
          <label className="field">
            <span>Start zone</span>
            <select
              value={selectedBench.start_zone ?? ''}
              onChange={(event) => updateSelectedBench((bench) => ({ ...bench, start_zone: event.target.value }))}
            >
              {zoneNames.map((name) => (
                <option key={`start-${name}`} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>End zone</span>
            <select
              value={selectedBench.end_zone ?? ''}
              onChange={(event) => updateSelectedBench((bench) => ({ ...bench, end_zone: event.target.value }))}
            >
              {zoneNames.map((name) => (
                <option key={`end-${name}`} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Add step</span>
            <select value={sequenceZone} onChange={(event) => setSequenceZone(event.target.value)}>
              {zoneNames.map((name) => (
                <option key={`sequence-${name}`} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary-button add-step-button" onClick={addSequenceStep}>
            Add Step
          </button>
        </div>

        <div className="sequence-list">
          {selectedBench.cycle_sequence.map((step, index) => (
            <div className="sequence-row" key={`${step}-${index}`}>
              <span>{index + 1}</span>
              <strong>{step}</strong>
              <button type="button" className="secondary-button compact-button" onClick={() => moveSequenceStep(index, -1)}>
                Up
              </button>
              <button type="button" className="secondary-button compact-button" onClick={() => moveSequenceStep(index, 1)}>
                Down
              </button>
              <button type="button" className="danger-button compact-button" onClick={() => removeSequenceStep(index)}>
                Remove
              </button>
            </div>
          ))}
        </div>

        <button type="button" className="primary-button save-button" disabled={isCommandPending} onClick={save}>
          {saved ? 'Saved' : 'Save Bench Configuration'}
        </button>
      </section>
    </section>
  )
}

function normalizeBenchCollection(collection) {
  if (collection?.benches?.length) {
    return {
      active_bench_id: collection.active_bench_id ?? collection.benches[0].id,
      benches: collection.benches.map(normalizeBench),
    }
  }

  if (collection?.zones) {
    const bench = normalizeBench({
      id: 'default',
      name: 'Bancada 1',
      zones: collection.zones,
      cycle_sequence: collection.cycle_sequence,
      start_zone: collection.start_zone,
      end_zone: collection.end_zone,
    })
    return { active_bench_id: bench.id, benches: [bench] }
  }

  const bench = normalizeBench({
    id: 'default',
    name: 'Bancada 1',
    zones: [],
    cycle_sequence: [],
    start_zone: null,
    end_zone: null,
  })
  return { active_bench_id: bench.id, benches: [bench] }
}

function normalizeBench(bench) {
  return {
    id: bench.id,
    name: bench.name,
    zones: bench.zones ?? [],
    cycle_sequence: bench.cycle_sequence ?? [],
    start_zone: bench.start_zone ?? bench.zones?.[0]?.name ?? null,
    end_zone: bench.end_zone ?? bench.zones?.at(-1)?.name ?? null,
  }
}

function duplicateBench(bench, index) {
  return {
    ...bench,
    id: createBenchId(),
    name: `Bancada ${index}`,
    zones: bench.zones.map((zone) => ({ ...zone })),
    cycle_sequence: [...bench.cycle_sequence],
  }
}

function createBenchId() {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID()
  }
  return `bench-${Date.now()}`
}

function createZoneModel(index, box) {
  return {
    name: `Zona ${index}`,
    ...box,
    two_hands: false,
  }
}

function eventToFramePoint(event) {
  const rect = event.currentTarget.getBoundingClientRect()
  return {
    x: Math.round(((event.clientX - rect.left) / rect.width) * FRAME_WIDTH),
    y: Math.round(((event.clientY - rect.top) / rect.height) * FRAME_HEIGHT),
  }
}

function boxFromPoints(startX, startY, endX, endY) {
  return {
    x: Math.min(startX, endX),
    y: Math.min(startY, endY),
    width: Math.abs(endX - startX),
    height: Math.abs(endY - startY),
  }
}

function clampBox(box) {
  const width = Math.max(1, Math.min(Math.round(box.width), FRAME_WIDTH))
  const height = Math.max(1, Math.min(Math.round(box.height), FRAME_HEIGHT))
  const x = Math.max(0, Math.min(Math.round(box.x), FRAME_WIDTH - width))
  const y = Math.max(0, Math.min(Math.round(box.y), FRAME_HEIGHT - height))
  return { x, y, width, height }
}

function boxStyle(box) {
  return {
    left: `${(box.x / FRAME_WIDTH) * 100}%`,
    top: `${(box.y / FRAME_HEIGHT) * 100}%`,
    width: `${(box.width / FRAME_WIDTH) * 100}%`,
    height: `${(box.height / FRAME_HEIGHT) * 100}%`,
  }
}
