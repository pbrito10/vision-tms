import { useState } from 'react'
import type { CSSProperties, PointerEvent } from 'react'
import { apiClient } from '../api/client'
import type { BenchConfig, BenchConfigResponse, BenchZone, FrameSize } from '../types'

const SNAPSHOT_STORAGE_KEY = 'vision-tms-bench-preview-snapshot'
const FALLBACK_FRAME_SIZE: FrameSize = { width: 640, height: 480 }

interface LegacyBenchConfigResponse {
  active_bench_id?: string | null
  zones?: BenchZone[]
  cycle_sequence?: string[]
  start_zone?: string | null
  end_zone?: string | null
  benches?: BenchConfig[]
}

interface Point {
  x: number
  y: number
}

interface Box {
  x: number
  y: number
  width: number
  height: number
}

type DragState =
  | {
      mode: 'pending-create'
      startX: number
      startY: number
      currentX: number
      currentY: number
    }
  | {
      mode: 'create'
      startX: number
      startY: number
      currentX: number
      currentY: number
    }
  | {
      mode: 'move'
      index: number
      startX: number
      startY: number
      original: Box
    }
  | {
      mode: 'resize'
      index: number
      startX: number
      startY: number
      original: Box
    }

interface BenchConfigViewProps {
  benchConfig: BenchConfigResponse
  cameraFrameSize: FrameSize
  isCommandPending: boolean
  onSave: (benchConfig: BenchConfigResponse) => Promise<BenchConfigResponse>
}

export function BenchConfigView({
  benchConfig,
  cameraFrameSize,
  isCommandPending,
  onSave,
}: BenchConfigViewProps) {
  const initialFrameSize = normalizeFrameSize(cameraFrameSize)
  const initialConfig = normalizeBenchCollection(benchConfig, initialFrameSize)
  const [draft, setDraft] = useState(initialConfig)
  const [selectedBenchId, setSelectedBenchId] = useState(initialConfig.active_bench_id)
  const [selectedZoneIndex, setSelectedZoneIndex] = useState(0)
  const [sequenceZone, setSequenceZone] = useState(initialConfig.benches[0]?.zones[0]?.name ?? '')
  const [snapshotImage, setSnapshotImage] = useState(loadStoredSnapshot)
  const [previewFrameSize, setPreviewFrameSize] = useState(initialFrameSize)
  const [snapshotError, setSnapshotError] = useState('')
  const [isSnapshotPending, setIsSnapshotPending] = useState(false)
  const [saved, setSaved] = useState(false)
  const [dragState, setDragState] = useState<DragState | null>(null)

  const selectedBench = draft.benches.find((bench) => bench.id === selectedBenchId)
    ?? draft.benches[0]
    ?? createEmptyBench()
  const selectedZone = selectedBench?.zones[selectedZoneIndex]
  const zoneNames = selectedBench?.zones.map((zone) => zone.name) ?? []
  const isActiveBench = selectedBench?.id === draft.active_bench_id
  const frameSize = previewFrameSize

  const selectBench = (benchId: string) => {
    const nextBench = draft.benches.find((bench) => bench.id === benchId)
      ?? draft.benches[0]
      ?? createEmptyBench()
    setSelectedBenchId(nextBench.id)
    setSelectedZoneIndex(0)
    setSequenceZone(nextBench.zones[0]?.name ?? '')
  }

  const updateSelectedBench = (updater: (bench: BenchConfig) => BenchConfig) => {
    setDraft((current) => ({
      ...current,
      benches: current.benches.map((bench) =>
        bench.id === selectedBench.id ? updater(bench) : bench,
      ),
    }))
  }

  const renameBench = (name: string) => {
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
    const nextSelected = remaining[0] ?? createEmptyBench()
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

  const updateZone = <K extends keyof BenchZone>(index: number, key: K, value: BenchZone[K]) => {
    updateSelectedBench((bench) => ({
      ...bench,
      zones: bench.zones.map((zone, zoneIndex) =>
        zoneIndex === index ? { ...zone, [key]: value } : zone,
      ),
    }))
  }

  const updateZoneBox = (index: number, nextBox: Box) => {
    updateSelectedBench((bench) => ({
      ...bench,
      zones: bench.zones.map((zone, zoneIndex) =>
        zoneIndex === index ? { ...zone, ...clampBox(nextBox, frameSize) } : zone,
      ),
    }))
  }

  const createZone = (box: Box) => {
    const zone = createZoneModel(selectedBench.zones.length + 1, clampBox(box, frameSize))
    updateSelectedBench((bench) => ({
      ...bench,
      zones: [...bench.zones, zone],
      start_zone: bench.start_zone ?? zone.name,
      end_zone: bench.end_zone ?? zone.name,
    }))
    setSequenceZone(zone.name)
    setSelectedZoneIndex(selectedBench.zones.length)
  }

  const removeZone = (index: number) => {
    const removed = selectedBench.zones[index]
    if (removed === undefined) {
      return
    }
    const nextZones = selectedBench.zones.filter((_, zoneIndex) => zoneIndex !== index)
    const nextNames = nextZones.map((zone) => zone.name)

    updateSelectedBench((bench) => ({
      ...bench,
      zones: nextZones,
      cycle_sequence: bench.cycle_sequence.filter((name) => name !== removed.name),
      cycle_repeat_rules: bench.cycle_repeat_rules
        .map((rule) => ({
          ...rule,
          sequence: rule.sequence.filter((name) => name !== removed.name),
        }))
        .filter((rule) => rule.sequence.length >= 2),
      start_zone: bench.start_zone !== null && nextNames.includes(bench.start_zone)
        ? bench.start_zone
        : nextNames[0] ?? null,
      end_zone: bench.end_zone !== null && nextNames.includes(bench.end_zone)
        ? bench.end_zone
        : nextNames.at(-1) ?? null,
    }))
    setSelectedZoneIndex(Math.max(0, index - 1))
    setSequenceZone(nextNames[0] ?? '')
  }

  const renameZone = (index: number, name: string) => {
    const previousName = selectedBench.zones[index]?.name
    if (previousName === undefined) {
      return
    }
    updateSelectedBench((bench) => ({
      ...bench,
      zones: bench.zones.map((zone, zoneIndex) =>
        zoneIndex === index ? { ...zone, name } : zone,
      ),
      cycle_sequence: bench.cycle_sequence.map((step) => (step === previousName ? name : step)),
      cycle_repeat_rules: bench.cycle_repeat_rules.map((rule) => ({
        ...rule,
        sequence: rule.sequence.map((step) => (step === previousName ? name : step)),
      })),
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

  const removeSequenceStep = (index: number) => {
    updateSelectedBench((bench) => ({
      ...bench,
      cycle_sequence: bench.cycle_sequence.filter((_, stepIndex) => stepIndex !== index),
    }))
  }

  const addRepeatRule = () => {
    if (!zoneNames.length) {
      return
    }
    updateSelectedBench((bench) => ({
      ...bench,
      cycle_repeat_rules: [
        ...bench.cycle_repeat_rules,
        {
          sequence: [zoneNames[0], zoneNames[1] ?? zoneNames[0]],
          min_repeats: 1,
          max_repeats: 4,
        },
      ],
    }))
  }

  const updateRepeatRule = (
    index: number,
    updater: (rule: BenchConfig['cycle_repeat_rules'][number]) => BenchConfig['cycle_repeat_rules'][number],
  ) => {
    updateSelectedBench((bench) => ({
      ...bench,
      cycle_repeat_rules: bench.cycle_repeat_rules.map((rule, ruleIndex) =>
        ruleIndex === index ? sanitizeRepeatRule(updater(rule)) : rule,
      ),
    }))
  }

  const removeRepeatRule = (index: number) => {
    updateSelectedBench((bench) => ({
      ...bench,
      cycle_repeat_rules: bench.cycle_repeat_rules.filter((_, ruleIndex) => ruleIndex !== index),
    }))
  }

  const moveSequenceStep = (index: number, direction: number) => {
    const target = index + direction
    if (target < 0 || target >= selectedBench.cycle_sequence.length) {
      return
    }
    updateSelectedBench((bench) => {
      const sequence = [...bench.cycle_sequence]
      const [item] = sequence.splice(index, 1)
      if (item === undefined) {
        return bench
      }
      sequence.splice(target, 0, item)
      return { ...bench, cycle_sequence: sequence }
    })
  }

  const save = async () => {
    try {
      const savedConfig = normalizeBenchCollection(await onSave(draft), frameSize)
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

  const MIN_CREATE_DISTANCE = 6

  const startDrawing = (event: PointerEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) {
      return
    }
    const point = eventToFramePoint(event, frameSize)
    setDragState({
      // start in a pending state so a simple click doesn't create a zone
      mode: 'pending-create',
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
    })
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const startMoving = (event: PointerEvent<HTMLButtonElement>, index: number) => {
    event.stopPropagation()
    setSelectedZoneIndex(index)
    const point = eventToFramePoint(event, frameSize)
    const zone = selectedBench.zones[index]
    if (zone === undefined) {
      return
    }
    setDragState({
      mode: 'move',
      index,
      startX: point.x,
      startY: point.y,
      original: { x: zone.x, y: zone.y, width: zone.width, height: zone.height },
    })
    // ensure pointer capture is on the preview container so pointermove events
    // are delivered to the container update handler
    const container = event.currentTarget.closest?.('.bench-preview') ?? event.currentTarget
    try {
      container.setPointerCapture(event.pointerId)
    } catch {
      // ignore if pointer capture isn't available
    }
  }

  const startResizing = (event: PointerEvent<HTMLSpanElement>, index: number) => {
    event.stopPropagation()
    setSelectedZoneIndex(index)
    const point = eventToFramePoint(event, frameSize)
    const zone = selectedBench.zones[index]
    if (zone === undefined) {
      return
    }
    setDragState({
      mode: 'resize',
      index,
      startX: point.x,
      startY: point.y,
      original: { x: zone.x, y: zone.y, width: zone.width, height: zone.height },
    })
    const container = event.currentTarget.closest?.('.bench-preview') ?? event.currentTarget
    try {
      container.setPointerCapture(event.pointerId)
    } catch {
      // ignore if pointer capture isn't available
    }
  }

  const updateDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragState) {
      return
    }

    const point = eventToFramePoint(event, frameSize)

    if (dragState.mode === 'pending-create') {
      const dx = point.x - dragState.startX
      const dy = point.y - dragState.startY
      if (Math.hypot(dx, dy) >= MIN_CREATE_DISTANCE) {
        // convert to an active create operation once the pointer has moved
        setDragState((current) => current === null
          ? current
          : { ...current, mode: 'create', currentX: point.x, currentY: point.y })
      }
      return
    }

    if (dragState.mode === 'create') {
      setDragState((current) => current === null
        ? current
        : {
            ...current,
            currentX: point.x,
            currentY: point.y,
          })
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

  const finishDrag = (event: PointerEvent<HTMLDivElement>) => {
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

  const captureSnapshot = async () => {
    setIsSnapshotPending(true)
    setSnapshotError('')

    try {
      const blob = await apiClient.getCameraSnapshot()
      const dataUrl = await blobToDataUrl(blob)
      storeSnapshot(dataUrl)
      setSnapshotImage(dataUrl)
    } catch (error) {
      if (!(error instanceof Error)) {
        setSnapshotError('Camera snapshot could not be loaded.')
        return
      }
      setSnapshotError(error.message)
    } finally {
      setIsSnapshotPending(false)
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
          {/* Add Zone button removed — use drag-to-create instead */}
        </div>

        <div className="zone-list">
          {selectedBench.zones.map((zone, index) => (
            <div className={`zone-row ${selectedZoneIndex === index ? 'is-selected' : ''}`} key={`zone-row-${index}`}>
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
          <div className="panel-heading-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={isSnapshotPending}
              onClick={captureSnapshot}
            >
              {isSnapshotPending ? 'Capturing' : 'Take Photo'}
            </button>
            <span className="result-pill">{selectedBench.zones.length} ZONES</span>
          </div>
        </div>
        {snapshotError && <p className="inline-error">{snapshotError}</p>}
        <div
          className="bench-preview"
          style={{ aspectRatio: `${frameSize.width} / ${frameSize.height}` }}
          onPointerDown={startDrawing}
          onPointerMove={updateDrag}
          onPointerUp={finishDrag}
          onPointerCancel={finishDrag}
        >
          {snapshotImage ? (
            <img
              className="bench-preview-camera"
              src={snapshotImage}
              alt=""
              draggable="false"
              onLoad={(event) => {
                setPreviewFrameSize(normalizeFrameSize({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                }))
              }}
            />
          ) : (
            <div className="bench-preview-empty">No photo</div>
          )}
          {selectedBench.zones.map((zone, index) => (
            <button
              type="button"
              className={`bench-zone ${selectedZoneIndex === index ? 'is-selected' : ''}`}
              key={`zone-preview-${index}`}
              style={boxStyle(zone, frameSize)}
              onPointerDown={(event) => startMoving(event, index)}
            >
              {zone.name}
              <span
                className="resize-handle"
                onPointerDown={(event) => startResizing(event, index)}
              ></span>
            </button>
          ))}
          {creationBox && <div className="bench-zone draft-zone" style={boxStyle(creationBox, frameSize)}></div>}
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

        <div className="repeat-rules-heading">
          <h3>Repeat rules</h3>
          <button
            type="button"
            className="secondary-button compact-button"
            disabled={!zoneNames.length}
            onClick={addRepeatRule}
          >
            Add Rule
          </button>
        </div>

        <div className="repeat-rule-list">
          {selectedBench.cycle_repeat_rules.map((rule, index) => (
            <div className="repeat-rule-row" key={`repeat-rule-${index}`}>
              <span>{index + 1}</span>
              <label className="field">
                <span>First</span>
                <select
                  value={rule.sequence[0] ?? ''}
                  onChange={(event) => updateRepeatRule(index, (current) => ({
                    ...current,
                    sequence: [event.target.value, current.sequence[1] ?? event.target.value],
                  }))}
                >
                  {zoneNames.map((name) => (
                    <option key={`repeat-first-${index}-${name}`} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Then</span>
                <select
                  value={rule.sequence[1] ?? rule.sequence[0] ?? ''}
                  onChange={(event) => updateRepeatRule(index, (current) => ({
                    ...current,
                    sequence: [current.sequence[0] ?? event.target.value, event.target.value],
                  }))}
                >
                  {zoneNames.map((name) => (
                    <option key={`repeat-then-${index}-${name}`} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field repeat-count-field">
                <span>Min</span>
                <input
                  min="1"
                  type="number"
                  value={rule.min_repeats}
                  onChange={(event) => updateRepeatRule(index, (current) => ({
                    ...current,
                    min_repeats: Number(event.target.value),
                  }))}
                />
              </label>
              <label className="field repeat-count-field">
                <span>Max</span>
                <input
                  min="1"
                  type="number"
                  value={rule.max_repeats}
                  onChange={(event) => updateRepeatRule(index, (current) => ({
                    ...current,
                    max_repeats: Number(event.target.value),
                  }))}
                />
              </label>
              <button type="button" className="danger-button compact-button" onClick={() => removeRepeatRule(index)}>
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

function loadStoredSnapshot(): string {
  try {
    return window.localStorage.getItem(SNAPSHOT_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

function storeSnapshot(dataUrl: string): void {
  try {
    window.localStorage.setItem(SNAPSHOT_STORAGE_KEY, dataUrl)
  } catch {
    // The preview still works even if the browser refuses local persistence.
  }
}

function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result)
        return
      }
      reject(new Error('Camera snapshot could not be loaded.'))
    }
    reader.onerror = () => reject(new Error('Camera snapshot could not be loaded.'))
    reader.readAsDataURL(blob)
  })
}

function normalizeBenchCollection(
  collection: LegacyBenchConfigResponse | BenchConfigResponse | null | undefined,
  frameSize: FrameSize,
): BenchConfigResponse {
  if (collection?.benches?.length) {
    return {
      active_bench_id: collection.active_bench_id ?? collection.benches[0].id,
      benches: collection.benches.map((bench) => normalizeBench(bench, frameSize)),
    }
  }

  if (isLegacyBenchCollection(collection)) {
    const bench = normalizeBench({
      id: 'default',
      name: 'Bancada 1',
      zones: collection.zones,
      cycle_sequence: collection.cycle_sequence,
      start_zone: collection.start_zone,
      end_zone: collection.end_zone,
    }, frameSize)
    return { active_bench_id: bench.id, benches: [bench] }
  }

  const bench = normalizeBench({
    id: 'default',
    name: 'Bancada 1',
    zones: [],
    cycle_sequence: [],
    start_zone: null,
    end_zone: null,
  }, frameSize)
  return { active_bench_id: bench.id, benches: [bench] }
}

function normalizeBench(bench: Partial<BenchConfig>, frameSize: FrameSize): BenchConfig {
  const zones = scaleLegacyZonesIfNeeded(bench.zones ?? [], frameSize)
  return {
    id: bench.id ?? createBenchId(),
    name: bench.name ?? 'Bancada 1',
    zones,
    cycle_sequence: bench.cycle_sequence ?? [],
    cycle_repeat_rules: (bench.cycle_repeat_rules ?? []).map(sanitizeRepeatRule),
    start_zone: bench.start_zone ?? zones[0]?.name ?? null,
    end_zone: bench.end_zone ?? zones.at(-1)?.name ?? null,
  }
}

function scaleLegacyZonesIfNeeded(zones: BenchZone[], frameSize: FrameSize): BenchZone[] {
  if (!zones.length) {
    return zones
  }
  if (frameSize.width === FALLBACK_FRAME_SIZE.width && frameSize.height === FALLBACK_FRAME_SIZE.height) {
    return zones
  }

  const maxRight = Math.max(...zones.map((zone) => zone.x + zone.width))
  const maxBottom = Math.max(...zones.map((zone) => zone.y + zone.height))
  const looksLikeLegacyFrame =
    maxRight <= FALLBACK_FRAME_SIZE.width
    && maxBottom <= FALLBACK_FRAME_SIZE.height
    && (
      maxRight >= FALLBACK_FRAME_SIZE.width * 0.9
      || maxBottom >= FALLBACK_FRAME_SIZE.height * 0.9
    )

  if (!looksLikeLegacyFrame) {
    return zones
  }

  const scaleX = frameSize.width / FALLBACK_FRAME_SIZE.width
  const scaleY = frameSize.height / FALLBACK_FRAME_SIZE.height
  return zones.map((zone) => ({
    ...zone,
    x: Math.round(zone.x * scaleX),
    y: Math.round(zone.y * scaleY),
    width: Math.round(zone.width * scaleX),
    height: Math.round(zone.height * scaleY),
  }))
}

function isLegacyBenchCollection(
  collection: LegacyBenchConfigResponse | BenchConfigResponse | null | undefined,
): collection is LegacyBenchConfigResponse & { zones: BenchZone[] } {
  return Array.isArray((collection as LegacyBenchConfigResponse | null | undefined)?.zones)
}

function duplicateBench(bench: BenchConfig, index: number): BenchConfig {
  return {
    ...bench,
    id: createBenchId(),
    name: `Bancada ${index}`,
    zones: bench.zones.map((zone) => ({ ...zone })),
    cycle_sequence: [...bench.cycle_sequence],
    cycle_repeat_rules: bench.cycle_repeat_rules.map((rule) => ({
      sequence: [...rule.sequence],
      min_repeats: rule.min_repeats,
      max_repeats: rule.max_repeats,
    })),
  }
}

function createBenchId(): string {
  if (window.crypto?.randomUUID) {
    return window.crypto.randomUUID()
  }
  return `bench-${Date.now()}`
}

function createZoneModel(index: number, box: Box): BenchZone {
  return {
    name: `Zona ${index}`,
    ...box,
    two_hands: false,
  }
}

function eventToFramePoint(event: PointerEvent<HTMLElement>, frameSize: FrameSize): Point {
  const rect = event.currentTarget.getBoundingClientRect()
  return {
    x: Math.round(((event.clientX - rect.left) / rect.width) * frameSize.width),
    y: Math.round(((event.clientY - rect.top) / rect.height) * frameSize.height),
  }
}

function boxFromPoints(startX: number, startY: number, endX: number, endY: number): Box {
  return {
    x: Math.min(startX, endX),
    y: Math.min(startY, endY),
    width: Math.abs(endX - startX),
    height: Math.abs(endY - startY),
  }
}

function clampBox(box: Box, frameSize: FrameSize): Box {
  const width = Math.max(1, Math.min(Math.round(box.width), frameSize.width))
  const height = Math.max(1, Math.min(Math.round(box.height), frameSize.height))
  const x = Math.max(0, Math.min(Math.round(box.x), frameSize.width - width))
  const y = Math.max(0, Math.min(Math.round(box.y), frameSize.height - height))
  return { x, y, width, height }
}

function boxStyle(box: Box, frameSize: FrameSize): CSSProperties {
  return {
    left: `${(box.x / frameSize.width) * 100}%`,
    top: `${(box.y / frameSize.height) * 100}%`,
    width: `${(box.width / frameSize.width) * 100}%`,
    height: `${(box.height / frameSize.height) * 100}%`,
  }
}

function normalizeFrameSize(frameSize: FrameSize | null | undefined): FrameSize {
  const width = Math.round(frameSize?.width ?? 0)
  const height = Math.round(frameSize?.height ?? 0)
  if (width <= 0 || height <= 0) {
    return FALLBACK_FRAME_SIZE
  }
  return { width, height }
}

function createEmptyBench(): BenchConfig {
  return {
    id: 'default',
    name: 'Bancada 1',
    zones: [],
    cycle_sequence: [],
    cycle_repeat_rules: [],
    start_zone: null,
    end_zone: null,
  }
}

function sanitizeRepeatRule(rule: BenchConfig['cycle_repeat_rules'][number]): BenchConfig['cycle_repeat_rules'][number] {
  const minRepeats = Math.max(1, Math.round(Number(rule.min_repeats) || 1))
  const maxRepeats = Math.max(minRepeats, Math.round(Number(rule.max_repeats) || minRepeats))
  return {
    sequence: rule.sequence.slice(0, 2),
    min_repeats: minRepeats,
    max_repeats: maxRepeats,
  }
}
