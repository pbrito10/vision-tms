export function MetricCard({ label, value, trend, tone }) {
  return (
    <article className={`metric-card ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{trend}</small>
    </article>
  )
}

export function InfoBlock({ label, value }) {
  return (
    <div className="info-block">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export function InspectionPreview({ compact = false, calibration = false }) {
  return (
    <div className={`inspection-preview ${compact ? 'compact' : ''} ${calibration ? 'calibration' : ''}`}>
      <div className="scan-grid" aria-hidden="true"></div>
      <div className="scan-line" aria-hidden="true"></div>
      <span className="target-box box-a"></span>
      <span className="target-box box-b"></span>
      <span className="target-box box-c"></span>
      {calibration && (
        <>
          <span className="crosshair horizontal"></span>
          <span className="crosshair vertical"></span>
        </>
      )}
      <div className="preview-footer">
        <span>CAM-01</span>
        <strong>1920 x 1080</strong>
      </div>
    </div>
  )
}

export function RangeField({ disabled = false, label, value, setValue, suffix, min, max, step = 1 }) {
  return (
    <label className="range-field">
      <span>
        {label}
        <strong>
          {value}
          {suffix}
        </strong>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => setValue(Number(event.target.value))}
      />
    </label>
  )
}

export function ToggleRow({ label, checked, onChange }) {
  return (
    <label className="toggle-row">
      <span>{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  )
}

export function Bar({ label, value, invert = false }) {
  const numericValue = Number.parseInt(value, 10)
  const fill = invert ? 100 - numericValue : numericValue

  return (
    <div className="bar-row">
      <span>
        {label}
        <strong>{value}</strong>
      </span>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${fill}%` }}></div>
      </div>
    </div>
  )
}

export function LogItem({ time, text }) {
  return (
    <div className="log-item">
      <time>{time}</time>
      <span>{text}</span>
    </div>
  )
}
