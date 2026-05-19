# Desenvolvimento

Este guia cobre o ciclo local de desenvolvimento do Vision TMS.

## Requisitos

- Docker com o contexto `default` configurado.
- Camara Linux disponivel como `/dev/video0`.
- Node e Python locais apenas para validacoes fora dos containers.

Confirma a camara com:

```bash
ls -l /dev/video*
```

Se estiver noutro device, atualiza `docker-compose.yml` e `backend/vision-tms-api/config/settings.yaml`.

## Stack Local

Subir a stack com rebuild:

```bash
docker --context default compose up -d --build
```

Subir sem rebuild, quando so mudaste codigo montado por volume:

```bash
docker --context default compose up -d
```

Ver estado e logs:

```bash
docker --context default compose ps
docker --context default compose logs -f backend
docker --context default compose logs -f frontend
```

Parar:

```bash
docker --context default compose down
```

## Quando Fazer Rebuild

Faz rebuild quando mudares:

- `backend/Dockerfile` ou `frontend/vision-tms-web/Dockerfile`
- `backend/vision-tms-api/requirements.txt`
- `frontend/vision-tms-web/package.json` ou `package-lock.json`
- Tags de imagens no `docker-compose.yml`

Mudancas normais em `backend/vision-tms-api` e `frontend/vision-tms-web/src` sao montadas no container e normalmente nao precisam de rebuild.

## Validacao

Backend:

```bash
PYTHONPYCACHEPREFIX=/tmp/vision-tms-pycache python3 -m compileall -q backend/vision-tms-api/api backend/vision-tms-api/src backend/vision-tms-api/*.py
```

Frontend:

```bash
npm --prefix frontend/vision-tms-web run typecheck
npm --prefix frontend/vision-tms-web run lint
npm --prefix frontend/vision-tms-web run build
```

Compose:

```bash
docker --context default compose config
```

## Ficheiros Gerados

O runtime escreve ficheiros fora do controlo de versao:

- `backend/vision-tms-api/output/`: Excel e CSV de debug.
- `backend/vision-tms-api/dashboard/data/`: frame e estado usados pelo stream do programa.
- Volumes Docker: dados de InfluxDB, Grafana e `node_modules` do frontend.

## Credenciais Locais

Credenciais de desenvolvimento:

- Grafana: `admin` / `vision-tms-admin`
- InfluxDB token: `vision-tms-dev-token`

Antes de producao, mover credenciais para `.env` ou secret manager.
