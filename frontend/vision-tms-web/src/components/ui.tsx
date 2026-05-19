interface InspectionPreviewProps {
  compact?: boolean
  calibration?: boolean
}

export function InspectionPreview({ compact = false, calibration = false }: InspectionPreviewProps) {
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
