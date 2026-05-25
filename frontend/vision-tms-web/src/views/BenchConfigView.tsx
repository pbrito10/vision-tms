import { useState } from 'react'
import type { BenchConfig, BenchConfigResponse, FrameSize } from '../types'
import { BenchLibraryPanel } from '../components/bench/BenchLibraryPanel'
import { BenchZonesPanel } from '../components/bench/BenchZonesPanel'
import { BenchPreviewPanel } from '../components/bench/BenchPreviewPanel'
import { BenchCyclePanel } from '../components/bench/BenchCyclePanel'
import {
  type Box,
  clampBox,
  createEmptyBench,
  createZoneModel,
  duplicateBench,
  normalizeBenchCollection,
  normalizeFrameSize,
} from '../components/bench/benchConfigUtils'

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
  const [frameSize, setFrameSize] = useState(initialFrameSize)
  const [saved, setSaved] = useState(false)

  const selectedBench = draft.benches.find((b) => b.id === selectedBenchId)
    ?? draft.benches[0]
    ?? createEmptyBench()
  const zoneNames = selectedBench.zones.map((z) => z.name)

  const updateSelectedBench = (updater: (bench: BenchConfig) => BenchConfig) => {
    setDraft((current) => ({
      ...current,
      benches: current.benches.map((b) => b.id === selectedBench.id ? updater(b) : b),
    }))
  }

  const selectBench = (benchId: string) => {
    const next = draft.benches.find((b) => b.id === benchId) ?? draft.benches[0] ?? createEmptyBench()
    setSelectedBenchId(next.id)
    setSelectedZoneIndex(0)
    setSequenceZone(next.zones[0]?.name ?? '')
  }

  const addBench = () => {
    const newBench = duplicateBench(selectedBench, draft.benches.length + 1)
    setDraft((current) => ({ ...current, benches: [...current.benches, newBench] }))
    setSelectedBenchId(newBench.id)
    setSelectedZoneIndex(0)
    setSequenceZone(newBench.zones[0]?.name ?? '')
  }

  const removeBench = () => {
    if (draft.benches.length <= 1) return
    const remaining = draft.benches.filter((b) => b.id !== selectedBench.id)
    const next = remaining[0] ?? createEmptyBench()
    setDraft((current) => ({
      ...current,
      active_bench_id: current.active_bench_id === selectedBench.id ? next.id : current.active_bench_id,
      benches: remaining,
    }))
    setSelectedBenchId(next.id)
    setSelectedZoneIndex(0)
    setSequenceZone(next.zones[0]?.name ?? '')
  }

  const renameZone = (index: number, name: string) => {
    const previousName = selectedBench.zones[index]?.name
    if (previousName === undefined) return
    updateSelectedBench((b) => ({
      ...b,
      zones: b.zones.map((z, i) => i === index ? { ...z, name } : z),
      cycle_sequence: b.cycle_sequence.map((step) => step === previousName ? name : step),
      cycle_repeat_rules: b.cycle_repeat_rules.map((rule) => ({
        ...rule,
        sequence: rule.sequence.map((step) => step === previousName ? name : step),
      })),
      start_zone: b.start_zone === previousName ? name : b.start_zone,
      end_zone: b.end_zone === previousName ? name : b.end_zone,
    }))
    if (sequenceZone === previousName) setSequenceZone(name)
  }

  const removeZone = (index: number) => {
    const removed = selectedBench.zones[index]
    if (removed === undefined) return
    const nextZones = selectedBench.zones.filter((_, i) => i !== index)
    const nextNames = nextZones.map((z) => z.name)
    updateSelectedBench((b) => ({
      ...b,
      zones: nextZones,
      cycle_sequence: b.cycle_sequence.filter((name) => name !== removed.name),
      cycle_repeat_rules: b.cycle_repeat_rules
        .map((rule) => ({ ...rule, sequence: rule.sequence.filter((name) => name !== removed.name) }))
        .filter((rule) => rule.sequence.length >= 2),
      start_zone: b.start_zone !== null && nextNames.includes(b.start_zone)
        ? b.start_zone : nextNames[0] ?? null,
      end_zone: b.end_zone !== null && nextNames.includes(b.end_zone)
        ? b.end_zone : nextNames.at(-1) ?? null,
    }))
    setSelectedZoneIndex(Math.max(0, index - 1))
    setSequenceZone(nextNames[0] ?? '')
  }

  const updateZoneBox = (index: number, nextBox: Box) => {
    updateSelectedBench((b) => ({
      ...b,
      zones: b.zones.map((z, i) => i === index ? { ...z, ...clampBox(nextBox, frameSize) } : z),
    }))
  }

  const createZone = (box: Box) => {
    const zone = createZoneModel(selectedBench.zones.length + 1, clampBox(box, frameSize))
    updateSelectedBench((b) => ({
      ...b,
      zones: [...b.zones, zone],
      start_zone: b.start_zone ?? zone.name,
      end_zone: b.end_zone ?? zone.name,
    }))
    setSequenceZone(zone.name)
    setSelectedZoneIndex(selectedBench.zones.length)
  }

  const handleSave = async () => {
    try {
      const savedConfig = normalizeBenchCollection(await onSave(draft), frameSize)
      const nextSelected = savedConfig.benches.find((b) => b.id === selectedBench.id)
        ?? savedConfig.benches.find((b) => b.id === savedConfig.active_bench_id)
        ?? savedConfig.benches[0]
      setDraft(savedConfig)
      setSelectedBenchId(nextSelected.id)
      setSaved(true)
      window.setTimeout(() => setSaved(false), 1800)
    } catch {
      setSaved(false)
    }
  }

  return (
    <section className="view-grid bench-grid">
      <BenchLibraryPanel
        benches={draft.benches}
        selectedBench={selectedBench}
        activeBenchId={draft.active_bench_id ?? ''}
        onSelectBench={selectBench}
        onRenameBench={(name) => updateSelectedBench((b) => ({ ...b, name }))}
        onAddBench={addBench}
        onRemoveBench={removeBench}
        onMarkAsActive={() => setDraft((current) => ({ ...current, active_bench_id: selectedBench.id }))}
      />
      <BenchZonesPanel
        zones={selectedBench.zones}
        selectedZoneIndex={selectedZoneIndex}
        onSelectZone={setSelectedZoneIndex}
        onRenameZone={renameZone}
        onToggleTwoHands={(index, checked) =>
          updateSelectedBench((b) => ({
            ...b,
            zones: b.zones.map((z, i) => i === index ? { ...z, two_hands: checked } : z),
          }))
        }
        onRemoveZone={removeZone}
      />
      <BenchPreviewPanel
        zones={selectedBench.zones}
        selectedZoneIndex={selectedZoneIndex}
        frameSize={frameSize}
        onSelectZone={setSelectedZoneIndex}
        onFrameSizeChange={setFrameSize}
        onCreateZone={createZone}
        onUpdateZoneBox={updateZoneBox}
      />
      <BenchCyclePanel
        bench={selectedBench}
        zoneNames={zoneNames}
        isCommandPending={isCommandPending}
        sequenceZone={sequenceZone}
        saved={saved}
        onSequenceZoneChange={setSequenceZone}
        onUpdateBench={updateSelectedBench}
        onSave={handleSave}
      />
    </section>
  )
}
