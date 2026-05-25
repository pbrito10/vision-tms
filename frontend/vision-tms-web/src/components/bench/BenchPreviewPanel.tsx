import { useState } from 'react'
import type { PointerEvent } from 'react'
import { apiClient } from '../../api/client'
import type { BenchZone, FrameSize } from '../../types'
import {
  type Box,
  type DragState,
  blobToDataUrl,
  boxFromPoints,
  boxStyle,
  eventToFramePoint,
  loadStoredSnapshot,
  normalizeFrameSize,
  storeSnapshot,
} from './benchConfigUtils'

const MIN_CREATE_DISTANCE = 6

interface BenchPreviewPanelProps {
  zones: BenchZone[]
  selectedZoneIndex: number
  frameSize: FrameSize
  onSelectZone: (index: number) => void
  onFrameSizeChange: (size: FrameSize) => void
  onCreateZone: (box: Box) => void
  onUpdateZoneBox: (index: number, box: Box) => void
}

export function BenchPreviewPanel({
  zones,
  selectedZoneIndex,
  frameSize,
  onSelectZone,
  onFrameSizeChange,
  onCreateZone,
  onUpdateZoneBox,
}: BenchPreviewPanelProps) {
  const [snapshotImage, setSnapshotImage] = useState(loadStoredSnapshot)
  const [snapshotError, setSnapshotError] = useState('')
  const [isSnapshotPending, setIsSnapshotPending] = useState(false)
  const [dragState, setDragState] = useState<DragState | null>(null)

  const selectedZone = zones[selectedZoneIndex]
  const creationBox = dragState?.mode === 'create'
    ? boxFromPoints(dragState.startX, dragState.startY, dragState.currentX, dragState.currentY)
    : null

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

  const startDrawing = (event: PointerEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return
    const point = eventToFramePoint(event, frameSize)
    setDragState({
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
    onSelectZone(index)
    const point = eventToFramePoint(event, frameSize)
    const zone = zones[index]
    if (zone === undefined) return
    setDragState({
      mode: 'move',
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

  const startResizing = (event: PointerEvent<HTMLSpanElement>, index: number) => {
    event.stopPropagation()
    onSelectZone(index)
    const point = eventToFramePoint(event, frameSize)
    const zone = zones[index]
    if (zone === undefined) return
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
    if (!dragState) return
    const point = eventToFramePoint(event, frameSize)

    if (dragState.mode === 'pending-create') {
      const dx = point.x - dragState.startX
      const dy = point.y - dragState.startY
      if (Math.hypot(dx, dy) >= MIN_CREATE_DISTANCE) {
        setDragState((current) => current === null
          ? current
          : { ...current, mode: 'create', currentX: point.x, currentY: point.y })
      }
      return
    }

    if (dragState.mode === 'create') {
      setDragState((current) => current === null
        ? current
        : { ...current, currentX: point.x, currentY: point.y })
      return
    }

    if (dragState.mode === 'move') {
      const dx = point.x - dragState.startX
      const dy = point.y - dragState.startY
      onUpdateZoneBox(dragState.index, {
        ...dragState.original,
        x: dragState.original.x + dx,
        y: dragState.original.y + dy,
      })
      return
    }

    if (dragState.mode === 'resize') {
      const dx = point.x - dragState.startX
      const dy = point.y - dragState.startY
      onUpdateZoneBox(dragState.index, {
        ...dragState.original,
        width: dragState.original.width + dx,
        height: dragState.original.height + dy,
      })
    }
  }

  const finishDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragState) return

    if (dragState.mode === 'create') {
      const box = boxFromPoints(
        dragState.startX,
        dragState.startY,
        dragState.currentX,
        dragState.currentY,
      )
      if (box.width >= 12 && box.height >= 12) {
        onCreateZone(box)
      }
    }

    setDragState(null)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }

  return (
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
          <span className="result-pill">{zones.length} ZONES</span>
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
              onFrameSizeChange(normalizeFrameSize({
                width: event.currentTarget.naturalWidth,
                height: event.currentTarget.naturalHeight,
              }))
            }}
          />
        ) : (
          <div className="bench-preview-empty">No photo</div>
        )}
        {zones.map((zone, index) => (
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
        {creationBox && (
          <div className="bench-zone draft-zone" style={boxStyle(creationBox, frameSize)}></div>
        )}
      </div>
    </section>
  )
}
