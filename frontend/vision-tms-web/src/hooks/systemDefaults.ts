import type {
  BenchConfigResponse,
  ProgramStateResponse,
  RuntimeStatus,
  SettingsResponse,
} from '../types'

export const emptyStatus: RuntimeStatus = {
  mode: 'idle',
  run_state: 'idle',
  active_program_id: null,
  active_bench_id: null,
  active_bench_name: null,
  message: 'API offline',
  updated_at: null,
  system_checks: [],
}

export const emptySettings: SettingsResponse = {
  system: {
    line_name: '',
    program_name: '',
    part_number: '',
    camera_serial: '',
  },
  camera: {
    index: 0,
    width: 640,
    height: 480,
    flip: false,
  },
  detection: {
    max_num_hands: 2,
    min_detection_confidence: 0.7,
    min_tracking_confidence: 0.7,
  },
  tracking: {
    dwell_time_seconds: 0.5,
    task_timeout_seconds: 30,
    stillness_threshold_px: 5,
    zones: [],
    two_hands_zones: [],
    cycle_zone_order: [],
    cycle_repeat_rules: [],
    start_zone: null,
    exit_zone: '',
  },
}

export const emptyBenchConfig: BenchConfigResponse = {
  active_bench_id: null,
  benches: [],
}

export const emptyProgramState: ProgramStateResponse = {
  captured_at: null,
  current_zone: null,
  current_step_index: null,
  completed_steps: [],
  expected_sequence: [],
  cycle_number: 1,
}
