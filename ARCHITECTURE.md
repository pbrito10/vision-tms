# Arquitetura

Vision TMS e composto por frontend React, API FastAPI, tres subprocessos de visao e stack de metricas com InfluxDB/Grafana.

## Fluxo Principal

```text
React/Vite
  -> FastAPI routes
  -> SystemService
  -> PipelineProcessManager
  -> capture_process -> detection_process -> monitor_process
  -> dashboard/data + InfluxDB + Excel
  -> FastAPI streams + Grafana
```

O frontend chama a API para configurar bancadas, iniciar/parar programa e receber atualizacoes live por SSE.

## Backend API

Os endpoints estao em `backend/vision-tms-api/api/routes.py`.

Os casos de uso foram separados por responsabilidade:

- `api/config_repository.py`: leitura/escrita de `config/settings.yaml`.
- `api/roi_service.py`: leitura, escrita e validacao de ROIs.
- `api/bench_repository.py`: persistencia e ativacao de bancadas.
- `api/camera_utils.py`: utilitarios de camara (ex: leitura do output_size da calibracao perspetiva).
- `api/config_validation.py`: validacao de configuracao de tracking antes de arrancar o pipeline.
- `api/program_state_repository.py`: leitura do estado leve publicado pelo monitor.
- `api/pipeline_process_manager.py`: ciclo de vida dos subprocessos.
- `api/system_service.py`: fachada de casos de uso consumida pelas rotas.
- `api/services.py`: montagem das instancias globais e compatibilidade de imports.

## Pipeline de Visao

O programa principal arranca tres subprocessos:

- `capture_process.py`: captura frames da camara e publica numa fila curta.
- `detection_process.py`: consome frames, deteta maos e publica deteccoes.
- `monitor_process.py`: classifica zonas, atualiza a state machine, calcula metricas e escreve outputs.

O `monitor_process.py` trata falhas de escrita de frame, estado, Excel e InfluxDB com logging, evitando que erros transientes de I/O terminem o processo.

## Estado e Outputs

Configuracao persistente:

- `config/settings.yaml`: parametros tecnicos do sistema.
- `config/benches.json`: bancadas configuradas via frontend.
- `config/rois.json`: ROIs ativas usadas pelo pipeline.

Dados gerados em runtime:

- `dashboard/data/program_frame.jpg`: frame anotado para `/api/program/stream`.
- `dashboard/data/program_state.json`: estado leve para `/api/program/state` e SSE.
- `output/`: Excel e CSV de debug por sessao.
- InfluxDB: metricas live para Grafana.

## Frontend

O ponto de entrada visual e `frontend/vision-tms-web/src/App.tsx`.

O estado do sistema e composto por hooks menores:

- `useSystemLiveData`: status, estado do programa e SSE.
- `useSystemConfiguration`: programas, settings e configuracao de bancadas.
- `useSystemCommands`: comandos start/stop e gravacao de bancadas.
- `useSystemData`: fachada que preserva a interface usada pela aplicacao.

As chamadas HTTP estao centralizadas em `src/api/client.ts`.

As vistas principais sao:

- `views/RunProgramView.tsx`: correr programa, ver stream anotado e estado em tempo real.
- `views/CameraTestView.tsx`: testar camara e validar posicionamento.
- `views/BenchConfigView.tsx`: configurar bancadas (zonas, sequencia de ciclo, regras de repeticao).

A configuracao de bancadas esta decomposta em paineis especializados:

- `components/bench/BenchPreviewPanel.tsx`: snapshot da camara, drag para criar/mover zonas sobre a imagem real.
- `components/bench/BenchZonesPanel.tsx`: lista de zonas, nome e flag duas maos.
- `components/bench/BenchCyclePanel.tsx`: sequencia do ciclo e regras de repeticao configuráveis.
- `components/bench/BenchLibraryPanel.tsx`: gerir bancadas salvas e escolher a ativa.
