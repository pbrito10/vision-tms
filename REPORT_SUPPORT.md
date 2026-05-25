# Apoio ao Relatório — Vision TMS

Documento de referência para escrever o relatório do projeto. Não é o relatório — é o mapa de factos, decisões e evidências que servem de base a cada secção.

---

## O que é o sistema

**Vision TMS** (Task Monitoring System) é um sistema de monitorização industrial por visão computacional. Usa uma câmara para detetar as mãos de um operador, acompanhar o progresso de uma tarefa de montagem zona a zona, medir o tempo de ciclo e publicar métricas em tempo real.

**Problema resolvido:** Verificar em tempo real se o operador executa os passos de montagem pela ordem certa, com as duas mãos nas zonas certas, no tempo esperado — sem sensores físicos na bancada.

---

## Stack tecnológica

| Camada | Tecnologia | Versão/detalhe |
|---|---|---|
| Backend API | FastAPI + Python | Uvicorn, Pydantic v2 |
| Visão computacional | MediaPipe | Deteção de landmarks de mãos |
| Frontend | React + TypeScript | Vite, hooks personalizados |
| Métricas | InfluxDB 2.7 | Time-series, bucket `vision_tms` |
| Dashboard | Grafana 13 | Provisioned, refresh mínimo 1s |
| Orquestração | Docker Compose | 4 serviços, volumes partilhados |

---

## Arquitetura — visão geral

```
Câmara (/dev/video0)
  └─ capture_process.py        (processo filho — captura frames)
       └─ detection_process.py  (processo filho — MediaPipe, publica deteções)
            └─ monitor_process.py (processo filho — classificação, state machine, métricas)
                  ├─ dashboard/data/program_frame.jpg   (stream MJPEG via API)
                  ├─ dashboard/data/program_state.json  (estado leve via SSE)
                  ├─ output/sessions/<timestamp>/       (Excel, CSV, vídeo)
                  └─ InfluxDB                           (métricas live → Grafana)

FastAPI (routes.py → system_service.py)
  ├─ SSE /api/events           (React polling 0.5s, diff antes de emitir)
  ├─ MJPEG /api/program/stream (frame anotado)
  └─ REST CRUD bancadas, settings, start/stop

React (Vite)
  ├─ useSystemLiveData          (SSE + estado programa)
  ├─ useSystemConfiguration     (bancadas, settings)
  ├─ useSystemCommands          (start/stop, save bench)
  └─ useSystemData              (fachada — interface estável para vistas)
```

**Decisão chave:** cada processo corre em spawn isolado — imports pesados (OpenCV, MediaPipe) não carregam no processo pai, reduzindo memória e tempo de arranque da API.

---

## Pipeline de visão — detalhe

### 1. Captura (`capture_process.py`)
- Abre câmara via OpenCV com índice e resolução de `settings.yaml`.
- Publica frames numa fila curta (sem acumulação) para o processo de deteção.

### 2. Deteção (`detection_process.py`)
- Consome frames da fila.
- Corre MediaPipe Hand Landmarker (`hand_landmarker.task`).
- Produz `HandDetection` com bounding box, keypoints e lado (left/right).
- Publica deteções numa fila para o monitor.

### 3. Monitor (`monitor_process.py`)
- Classifica cada deteção numa zona ROI (`ZoneClassifier`).
- Atualiza a state machine por zona (`OneHandStateMachine` / `TwoHandsStateMachine`).
- Rastreia eventos de tarefa (`TaskEvent`) e agrega-os em ciclos (`CycleTracker`).
- Calcula métricas (`MetricsCalculator`) e publica no InfluxDB.
- Escreve frame anotado e estado JSON para o stream da API.
- Persiste Excel e CSV de debug por sessão.

### Módulos de tracking (`src/tracking/`)

| Módulo | Responsabilidade |
|---|---|
| `zone_classifier.py` | Mapeia coordenadas de mão → zona ROI |
| `task_state_machine.py` | Dwell time, timeout, stillness, validação 1/2 mãos |
| `activation_strategy.py` | Estratégia de ativação (1 mão vs 2 mãos) |
| `cycle_tracker.py` | Sequência de zonas, repeat rules, abertura/fecho de ciclos |
| `order_matching.py` | Verificação de ordem com suporte a blocos repetíveis |
| `task_event.py` / `task_event_merger.py` | Eventos de tarefa e fusão |
| `task_labeler.py` | Associa etiquetas às tarefas de montagem |
| `task_diagnostic.py` | Diagnósticos de rejeição (timeout, saída antecipada, etc.) |

### Parâmetros configuráveis de tracking

- `dwell_time_seconds`: tempo que a mão tem de estar parada na zona para validar.
- `stillness_threshold_px`: deslocamento máximo permitido durante dwell.
- `task_timeout_seconds`: tempo máximo em zona antes de timeout.
- `two_hands_missing_tolerance_seconds`: folga para a segunda mão chegar.
- `cycle_repeat_rules`: blocos da sequência que podem repetir N vezes (ex: sub-montagem).
- `start_zone` / `exit_zone`: zona que inicia e fecha o ciclo.

---

## Configuração de bancadas

Uma bancada define as zonas da bancada de trabalho e a sequência esperada do ciclo.

**Fluxo de configuração (frontend → backend):**
1. `BenchPreviewPanel`: utilizador tira snapshot da câmara, arrasta para criar zonas sobre a imagem real.
2. `BenchZonesPanel`: nomeia zonas, marca quais precisam de duas mãos.
3. `BenchCyclePanel`: define ordem do ciclo e regras de repetição.
4. `BenchLibraryPanel`: guarda bancada, escolhe a bancada ativa.

**No backend (`bench_repository.py`):**
- Persiste em `config/benches.json` (fora do Git).
- Deriva `assembly_zone` e `assembly_task_labels` automaticamente a partir das zonas.
- Escala zonas se houver calibração de perspetiva (lê `output_size` do `.npz`).
- Gera `rois.json` a partir das zonas da bancada ativa, usado pelo pipeline.

---

## API REST — endpoints principais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/health` | Saúde do serviço |
| GET | `/api/system/status` | Modo (idle/program/camera_test) e estado |
| GET | `/api/programs` | Lista de programas disponíveis |
| POST | `/api/program/start` | Arrancar programa (program_id + bench_id) |
| POST | `/api/program/stop` | Parar programa |
| POST | `/api/camera-test/start` | Iniciar modo câmara |
| POST | `/api/camera-test/stop` | Parar modo câmara |
| GET | `/api/camera/stream` | MJPEG stream (modo câmara) |
| GET | `/api/camera/snapshot` | Snapshot único (modo idle) |
| GET | `/api/program/stream` | MJPEG stream anotado (programa a correr) |
| GET | `/api/program/state` | Estado atual do programa (zona, passo, ciclo) |
| GET | `/api/events` | SSE — atualizações live do sistema |
| GET/PUT | `/api/bench-config` | Ler/guardar configuração de bancadas |
| GET | `/api/settings` | Settings técnicos do sistema |

**SSE (`/api/events`):** diff antes de emitir (evita flooding), heartbeat a cada 15s se não houver mudança.

---

## Outputs gerados

| Output | Localização | Conteúdo |
|---|---|---|
| Frame anotado | `dashboard/data/program_frame.jpg` | Frame com zonas e estado desenhados |
| Estado JSON | `dashboard/data/program_state.json` | Zona atual, passo, ciclo |
| Excel | `output/sessions/<ts>/` | Métricas por ciclo e tarefa |
| CSV debug | `output/sessions/<ts>/` | Eventos frame a frame |
| Vídeo anotado | `output/sessions/<ts>/` | Gravação da sessão |
| Gaps | `output/sessions/<ts>/gaps/` | Frames de períodos sem deteção |
| InfluxDB | bucket `vision_tms` | Métricas live para Grafana |

---

## Grafana

Dashboard provisionado em `grafana/provisioning/`. Visualiza métricas em tempo real: tempo de ciclo, tempo por zona, desvios, produtividade.

Refresh mínimo configurado para 1s (`GF_DASHBOARDS_MIN_REFRESH_INTERVAL`).

---

## Decisões de design relevantes para o relatório

### Processos filhos isolados
**Porquê:** MediaPipe e OpenCV têm inicialização pesada. Spawn isolado evita carregar estas dependências no processo da API. Cada processo tem responsabilidade única (captura / deteção / monitorização).

### SSE em vez de WebSocket
**Porquê:** unidirecional (servidor → cliente) é suficiente para estado. SSE é mais simples de implementar e de manter em FastAPI. O cliente usa REST para comandos.

### Configuração de bancadas fora do Git
**Porquê:** cada PC tem câmara diferente e bancada física diferente. Versionar `benches.json` e `rois.json` causaria conflitos constantes entre máquinas de desenvolvimento.

### Dwell time + stillness
**Porquê:** evitar falsos positivos por passagem rápida da mão sobre a zona. A mão tem de estar parada (dentro de `stillness_threshold_px`) durante `dwell_time_seconds`.

### Repeat rules no ciclo
**Porquê:** alguns passos de montagem repetem-se N vezes antes de avançar (ex: apertar X parafusos). Regras configuráveis evitam criar programas separados para variações de quantidade.

### Calibração de perspetiva
**Porquê:** câmara com ângulo oblíquo distorce as coordenadas. A calibração corrige a perspetiva para que as zonas definidas sobre o snapshot correspondam à posição real na bancada.

---

## O que está implementado além do básico

- Suporte a **duas mãos** por zona com tolerância configurável.
- **Repeat rules**: blocos da sequência com min/max repetições.
- **Diagnósticos de rejeição**: razão por que uma tarefa não validou (timeout, saída antes de stillness, segunda mão em falta, etc.).
- **Calibração de perspetiva** e de lente (scripts em `calibration/`).
- **Deteção de gaps**: períodos sem mãos detetadas são registados com frames de evidência.
- **Excel por sessão** com métricas detalhadas por ciclo e tarefa.
- **Dashboard Grafana** provisionado automaticamente.
- **Preview ao vivo** da câmara no frontend durante configuração de bancada.
- **Snapshot persistido** no browser para configurar zonas sem a câmara ligada.
- **Validação de configuração** antes de arrancar pipeline (evita erros em runtime).

---

## Estrutura de ficheiros relevante (resumo)

```
vision-tms/
├── backend/vision-tms-api/
│   ├── api/                    # FastAPI: rotas, serviços, repositórios
│   ├── src/
│   │   ├── detection/          # MediaPipe wrapper, tipos de deteção
│   │   ├── tracking/           # State machine, ciclos, eventos
│   │   ├── metrics/            # Cálculo de métricas
│   │   ├── roi/                # ROI model e repositório
│   │   └── shared/             # Tipos partilhados (TaskState, etc.)
│   ├── capture_process.py      # Processo de captura
│   ├── detection_process.py    # Processo de deteção
│   ├── monitor_process.py      # Processo de monitorização
│   ├── process_entrypoints.py  # Entrypoints dos subprocessos
│   ├── calibration/            # Scripts de calibração
│   └── config/                 # settings.yaml (versionado)
├── frontend/vision-tms-web/
│   └── src/
│       ├── views/              # RunProgram, CameraTest, BenchConfig
│       ├── components/bench/   # Painéis de configuração de bancada
│       ├── hooks/              # Estado do sistema (SSE, commands, config)
│       └── api/client.ts       # Chamadas HTTP
├── grafana/provisioning/       # Dashboard e datasource provisionados
└── docker-compose.yml          # Stack: backend, frontend, InfluxDB, Grafana
```
