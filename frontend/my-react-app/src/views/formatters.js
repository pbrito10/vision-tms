export function formatSeconds(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }

  if (value >= 60) {
    const minutes = Math.floor(value / 60)
    const seconds = Math.round(value % 60)
    return `${minutes}m ${String(seconds).padStart(2, '0')}s`
  }

  return `${Number(value).toFixed(1)}s`
}

export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '-'
  }
  return `${Number(value).toFixed(1)}%`
}

export function orderYield(cycleMetrics) {
  if (!cycleMetrics.count) {
    return null
  }
  return (cycleMetrics.count_in_order / cycleMetrics.count) * 100
}

