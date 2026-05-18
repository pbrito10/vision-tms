import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient } from '../api/client'
import { InspectionPreview } from '../components/ui'

export function CameraTestView({
  isCommandPending,
  onStartCameraTest,
  onStopCameraTest,
  settings,
  status,
}) {
  const isCameraTestRunning = status.mode === 'camera_test' && status.run_state === 'running'

  return (
    <section className="view-grid camera-grid">
      <section className="panel camera-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Camera test</p>
            <h2>{settings.system.camera_serial || 'CAM-01'}</h2>
          </div>
          <span className="result-pill">{isCameraTestRunning ? 'RUNNING' : 'READY'}</span>
        </div>
        {isCameraTestRunning ? (
          <div className="camera-stream">
            <CameraStreamImage />
          </div>
        ) : (
          <InspectionPreview calibration />
        )}
        <div className="control-buttons">
          <button
            type="button"
            className="primary-button"
            disabled={isCameraTestRunning || isCommandPending}
            onClick={onStartCameraTest}
          >
            Start Camera Test
          </button>
          <button
            type="button"
            className="danger-button"
            disabled={!isCameraTestRunning || isCommandPending}
            onClick={onStopCameraTest}
          >
            Stop Camera Test
          </button>
        </div>
      </section>
    </section>
  )
}

function CameraStreamImage() {
  const [streamRevision, setStreamRevision] = useState(Math.random())
  const reconnectTimeoutRef = useRef(null)

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      return
    }

    reconnectTimeoutRef.current = window.setTimeout(() => {
      reconnectTimeoutRef.current = null
      setStreamRevision(Math.random())
    }, 1000)
  }, [])

  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [])

  const streamUrl = `${apiClient.cameraStreamUrl()}?retry=${streamRevision}`

  return (
    <img
      key={streamRevision}
      src={streamUrl}
      alt="Camera live stream"
      onError={reconnect}
    />
  )
}
