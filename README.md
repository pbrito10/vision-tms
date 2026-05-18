# Vision TMS

Vision TMS é um sistema de monitorização de tarefas industriais. Usa uma câmara para detetar mãos, acompanhar zonas de uma bancada, medir ciclos de execução e publicar métricas em tempo real.

O projeto está dividido em quatro partes:

- `backend/vision-tms-api`: backend FastAPI e pipeline de visão.
- `frontend/vision-tms-web`: interface React/Vite.
- `grafana/provisioning`: datasource e dashboard do Grafana.
- `docker-compose.yml`: stack local com backend, frontend, InfluxDB e Grafana.

## Serviços

| Serviço | URL | Função |
| --- | --- | --- |
| Frontend | `http://localhost:5173` | Correr programa, testar câmara e configurar bancadas |
| Backend API | `http://localhost:8000` | API FastAPI para câmara, programa e configuração |
| Grafana | `http://localhost:3000` | Dashboard do operador |
| InfluxDB | `http://localhost:8086` | Base de dados temporal para métricas |

Credenciais de desenvolvimento do Grafana:

- Utilizador: `admin`
- Password: `vision-tms-admin`

## Requisitos

- Docker com o contexto `default` disponível.
- Câmara Linux disponível como `/dev/video0`.
- Node/Python localmente apenas se quiseres correr validações fora do Docker.

Para confirmar a câmara:

```bash
ls -l /dev/video*
```

Se a câmara não estiver em `/dev/video0`, altera:

- `docker-compose.yml`, em `services.backend.devices`
- `backend/vision-tms-api/config/settings.yaml`, em `camera.index`

## Como Correr

Na raiz do repositório:

```bash
docker --context default compose up -d --build
```

Depois do primeiro build, o código fica montado nos containers. Para mudanças normais no código, normalmente basta:

```bash
docker --context default compose up -d
```

Comandos úteis:

```bash
docker --context default compose ps
docker --context default compose logs -f backend
docker --context default compose logs -f frontend
docker --context default compose down
```

## Backend

O backend está em `backend/vision-tms-api` e é montado no container em `/app`.

Ficheiros principais:

- `api/main.py`: criação da app FastAPI.
- `api/routes.py`: rotas HTTP.
- `api/services.py`: casos de uso da aplicação.
- `process_entrypoints.py`: entrypoints dos subprocessos.
- `monitor_process.py`: tracking, métricas, Excel e publicação para InfluxDB.

Ficheiros gerados em runtime e ignorados pelo Git:

- `backend/vision-tms-api/output/`
- `backend/vision-tms-api/dashboard/data/`
- `backend/vision-tms-api/core*`
- caches Python

## Frontend

O frontend está em `frontend/vision-tms-web` e é montado no container em `/app`.

Validação local:

```bash
npm --prefix frontend/vision-tms-web run lint
npm --prefix frontend/vision-tms-web run build
```

## Validação

Antes de enviar alterações:

```bash
PYTHONPYCACHEPREFIX=/tmp/vision-tms-pycache python3 -m compileall -q backend/vision-tms-api/api backend/vision-tms-api/src backend/vision-tms-api/*.py
npm --prefix frontend/vision-tms-web run lint
npm --prefix frontend/vision-tms-web run build
docker --context default compose config
```

## Logging

O backend usa `logging` em vez de `print()`. O nível pode ser alterado no `docker-compose.yml` através de:

```yaml
VISION_TMS_LOG_LEVEL: INFO
```

Valores úteis: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

## Notas

- O backend deve correr com o contexto Docker `default`, para conseguir mapear a câmara.
- O código do backend e frontend está montado nos containers; só precisas de rebuild quando mudas dependências ou Dockerfiles.
- InfluxDB e Grafana ainda usam credenciais de desenvolvimento no `docker-compose.yml`. Antes de produção, estas credenciais devem passar para `.env`.
