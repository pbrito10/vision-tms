import type { BenchConfig } from '../../types'
import { sanitizeRepeatRule } from './benchConfigUtils'

interface BenchCyclePanelProps {
  bench: BenchConfig
  zoneNames: string[]
  isCommandPending: boolean
  sequenceZone: string
  saved: boolean
  onSequenceZoneChange: (zone: string) => void
  onUpdateBench: (updater: (bench: BenchConfig) => BenchConfig) => void
  onSave: () => void
}

export function BenchCyclePanel({
  bench,
  zoneNames,
  isCommandPending,
  sequenceZone,
  saved,
  onSequenceZoneChange,
  onUpdateBench,
  onSave,
}: BenchCyclePanelProps) {
  const addSequenceStep = () => {
    if (!sequenceZone) return
    onUpdateBench((b) => ({ ...b, cycle_sequence: [...b.cycle_sequence, sequenceZone] }))
  }

  const removeSequenceStep = (index: number) => {
    onUpdateBench((b) => ({
      ...b,
      cycle_sequence: b.cycle_sequence.filter((_, i) => i !== index),
    }))
  }

  const moveSequenceStep = (index: number, direction: number) => {
    const target = index + direction
    if (target < 0 || target >= bench.cycle_sequence.length) return
    onUpdateBench((b) => {
      const sequence = [...b.cycle_sequence]
      const [item] = sequence.splice(index, 1)
      if (item === undefined) return b
      sequence.splice(target, 0, item)
      return { ...b, cycle_sequence: sequence }
    })
  }

  const addRepeatRule = () => {
    if (!zoneNames.length) return
    onUpdateBench((b) => ({
      ...b,
      cycle_repeat_rules: [
        ...b.cycle_repeat_rules,
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
    onUpdateBench((b) => ({
      ...b,
      cycle_repeat_rules: b.cycle_repeat_rules.map((rule, i) =>
        i === index ? sanitizeRepeatRule(updater(rule)) : rule,
      ),
    }))
  }

  const removeRepeatRule = (index: number) => {
    onUpdateBench((b) => ({
      ...b,
      cycle_repeat_rules: b.cycle_repeat_rules.filter((_, i) => i !== index),
    }))
  }

  return (
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
            value={bench.start_zone ?? ''}
            onChange={(event) => onUpdateBench((b) => ({ ...b, start_zone: event.target.value }))}
          >
            {zoneNames.map((name) => (
              <option key={`start-${name}`} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>End zone</span>
          <select
            value={bench.end_zone ?? ''}
            onChange={(event) => onUpdateBench((b) => ({ ...b, end_zone: event.target.value }))}
          >
            {zoneNames.map((name) => (
              <option key={`end-${name}`} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Add step</span>
          <select value={sequenceZone} onChange={(event) => onSequenceZoneChange(event.target.value)}>
            {zoneNames.map((name) => (
              <option key={`sequence-${name}`} value={name}>{name}</option>
            ))}
          </select>
        </label>
        <button type="button" className="secondary-button add-step-button" onClick={addSequenceStep}>
          Add Step
        </button>
      </div>

      <div className="sequence-list">
        {bench.cycle_sequence.map((step, index) => (
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
        {bench.cycle_repeat_rules.map((rule, index) => (
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
                  <option key={`repeat-first-${index}-${name}`} value={name}>{name}</option>
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
                  <option key={`repeat-then-${index}-${name}`} value={name}>{name}</option>
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

      <button
        type="button"
        className="primary-button save-button"
        disabled={isCommandPending}
        onClick={onSave}
      >
        {saved ? 'Saved' : 'Save Bench Configuration'}
      </button>
    </section>
  )
}
