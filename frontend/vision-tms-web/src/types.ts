export type RuntimeState = 'idle' | 'running' | 'stopping' | 'error'

export type RuntimeMode = 'idle' | 'program' | 'camera_test'

export type CheckStatus = 'ok' | 'warning' | 'error'

export type AppView = 'run' | 'camera' | 'bench'

export interface FrameSize {
  width: number
  height: number
}

export interface SystemCheck {
  name: string
  value: string
  status: CheckStatus
}

export interface RuntimeStatus {
  mode: RuntimeMode
  run_state: RuntimeState
  active_program_id: string | null
  active_bench_id: string | null
  active_bench_name: string | null
  message: string
  updated_at: string | null
  system_checks: SystemCheck[]
}

export interface Program {
  id: string
  name: string
  part_number: string
  tolerance: string
  zone_order: string[]
  start_zone: string | null
  exit_zone: string
  two_hands_zones: string[]
}

export interface CameraSettings {
  index: number
  width: number
  height: number
  flip: boolean
}

export interface DetectionSettings {
  max_num_hands: number
  min_detection_confidence: number
  min_tracking_confidence: number
}

export interface TrackingSettings {
  dwell_time_seconds: number
  task_timeout_seconds: number
  stillness_threshold_px: number
  zones: string[]
  two_hands_zones: string[]
  cycle_zone_order: string[]
  start_zone: string | null
  exit_zone: string
}

export interface SystemSettings {
  line_name: string
  program_name: string
  part_number: string
  camera_serial: string
}

export interface SettingsResponse {
  system: SystemSettings
  camera: CameraSettings
  detection: DetectionSettings
  tracking: TrackingSettings
}

export interface BenchZone {
  name: string
  x: number
  y: number
  width: number
  height: number
  two_hands: boolean
}

export interface BenchConfig {
  id: string
  name: string
  zones: BenchZone[]
  cycle_sequence: string[]
  start_zone: string | null
  end_zone: string | null
}

export interface BenchConfigResponse {
  active_bench_id: string | null
  benches: BenchConfig[]
}

export interface ProgramStateResponse {
  captured_at: string | null
  current_zone: string | null
  current_step_index: number | null
  completed_steps: string[]
  expected_sequence: string[]
  cycle_number: number
}

export interface CommandResponse {
  accepted: boolean
  status: RuntimeStatus
}

export interface LiveSnapshot {
  status?: RuntimeStatus
  program_state?: ProgramStateResponse
}
