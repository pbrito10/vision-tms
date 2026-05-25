import type { CSSProperties, PointerEvent } from 'react'
import type { BenchConfig, BenchConfigResponse, BenchZone, FrameSize } from '../../types'

export const SNAPSHOT_STORAGE_KEY = 'vision-tms-bench-preview-snapshot'
export const FALLBACK_FRAME_SIZE: FrameSize = { width: 640, height: 480 }

export interface LegacyBenchConfigResponse {
  active_bench_id?: string | null
  zones?: BenchZone[]
  cycle_sequence?: string[]
  start_zone?: string | null
  end_zone?: string | null
  benches?: BenchConfig[]
}

export interface Point {
  x: number
  y: number
}

export interface Box {
  x: number
  y: number
  width: number
  height: number
}

export type DragState =
  | { mode: 'pending-create'; startX: number; startY: number; currentX: number; currentY: number }
  | { mode: 'create'; startX: number; startY: number; currentX: number; currentY: number }
  | { mode: 'move'; index: number; startX: number; startY: number; original: Box }
  | { mode: 'resize'; index: number; startX: number; startY: number; original: Box }

export function loadStoredSnapshot(): string {
  try {
    return window.localStorage.getItem(SNAPSHOT_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function storeSnapshot(dataUrl: string): void {
  try {
    window.localStorage.setItem(SNAPSHOT_STORAGE_KEY, dataUrl)
  } catch {
    // preview still works without local persistence
  }
}

export function blobToDataUrl(blob: Blob): Promise<string> {
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

export function normalizeBenchCollection(
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

export function normalizeBench(bench: Partial<BenchConfig>, frameSize: FrameSize): BenchConfig {
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

export function scaleLegacyZonesIfNeeded(zones: BenchZone[], frameSize: FrameSize): BenchZone[] {
  if (!zones.length) return zones
  if (frameSize.width === FALLBACK_FRAME_SIZE.width && frameSize.height === FALLBACK_FRAME_SIZE.height) {
    return zones
  }

  const maxRight = Math.max(...zones.map((zone) => zone.x + zone.width))
  const maxBottom = Math.max(...zones.map((zone) => zone.y + zone.height))
  const looksLikeLegacyFrame =
    maxRight <= FALLBACK_FRAME_SIZE.width
    && maxBottom <= FALLBACK_FRAME_SIZE.height
    && (maxRight >= FALLBACK_FRAME_SIZE.width * 0.9 || maxBottom >= FALLBACK_FRAME_SIZE.height * 0.9)

  if (!looksLikeLegacyFrame) return zones

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

export function isLegacyBenchCollection(
  collection: LegacyBenchConfigResponse | BenchConfigResponse | null | undefined,
): collection is LegacyBenchConfigResponse & { zones: BenchZone[] } {
  return Array.isArray((collection as LegacyBenchConfigResponse | null | undefined)?.zones)
}

export function duplicateBench(bench: BenchConfig, index: number): BenchConfig {
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

export function createBenchId(): string {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID()
  return `bench-${Date.now()}`
}

export function createZoneModel(index: number, box: Box): BenchZone {
  return { name: `Zona ${index}`, ...box, two_hands: false }
}

export function eventToFramePoint(event: PointerEvent<HTMLElement>, frameSize: FrameSize): Point {
  const rect = event.currentTarget.getBoundingClientRect()
  return {
    x: Math.round(((event.clientX - rect.left) / rect.width) * frameSize.width),
    y: Math.round(((event.clientY - rect.top) / rect.height) * frameSize.height),
  }
}

export function boxFromPoints(startX: number, startY: number, endX: number, endY: number): Box {
  return {
    x: Math.min(startX, endX),
    y: Math.min(startY, endY),
    width: Math.abs(endX - startX),
    height: Math.abs(endY - startY),
  }
}

export function clampBox(box: Box, frameSize: FrameSize): Box {
  const width = Math.max(1, Math.min(Math.round(box.width), frameSize.width))
  const height = Math.max(1, Math.min(Math.round(box.height), frameSize.height))
  const x = Math.max(0, Math.min(Math.round(box.x), frameSize.width - width))
  const y = Math.max(0, Math.min(Math.round(box.y), frameSize.height - height))
  return { x, y, width, height }
}

export function boxStyle(box: Box, frameSize: FrameSize): CSSProperties {
  return {
    left: `${(box.x / frameSize.width) * 100}%`,
    top: `${(box.y / frameSize.height) * 100}%`,
    width: `${(box.width / frameSize.width) * 100}%`,
    height: `${(box.height / frameSize.height) * 100}%`,
  }
}

export function normalizeFrameSize(frameSize: FrameSize | null | undefined): FrameSize {
  const width = Math.round(frameSize?.width ?? 0)
  const height = Math.round(frameSize?.height ?? 0)
  if (width <= 0 || height <= 0) return FALLBACK_FRAME_SIZE
  return { width, height }
}

export function createEmptyBench(): BenchConfig {
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

export function sanitizeRepeatRule(
  rule: BenchConfig['cycle_repeat_rules'][number],
): BenchConfig['cycle_repeat_rules'][number] {
  const minRepeats = Math.max(1, Math.round(Number(rule.min_repeats) || 1))
  const maxRepeats = Math.max(minRepeats, Math.round(Number(rule.max_repeats) || minRepeats))
  return {
    sequence: rule.sequence.slice(0, 2),
    min_repeats: minRepeats,
    max_repeats: maxRepeats,
  }
}
