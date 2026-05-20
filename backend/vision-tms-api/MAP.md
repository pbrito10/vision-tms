# Vision TMS - mapa atual

Este backend corre como API FastAPI e comunica com o frontend React, InfluxDB e Grafana.
O fluxo antigo de menu Python/Streamlit foi removido.

## Entrada da API

- `api/main.py`: cria a aplicação FastAPI.
- `api/routes.py`: expõe saúde, estado, câmara, programa e configuração de bancadas.
- `api/system_service.py`: casos de uso da aplicação consumidos pelas rotas.
- `api/services.py`: montagem das instâncias globais e compatibilidade de imports.
- `api/config_repository.py`: persistência de `settings.yaml`.
- `api/bench_repository.py`: persistência e ativação de bancadas.
- `api/roi_service.py`: persistência e validação de ROIs.
- `api/pipeline_process_manager.py`: gestão dos subprocessos.
- `process_entrypoints.py`: entrypoints limpos para os subprocessos do pipeline.

## Pipeline de visão

- `capture_process.py`: captura frames da câmara.
- `detection_process.py`: deteta mãos nos frames.
- `monitor_process.py`: classifica zonas, controla o ciclo, publica imagem/estado e escreve métricas.

## Configuração

- `config/settings.yaml`: parâmetros técnicos versionados.
- `config/benches.json`: bancadas locais guardadas pelo frontend e ignoradas pelo Git.
- `config/rois.json`: ROIs locais geradas a partir da bancada escolhida e ignoradas pelo Git.

## Saídas

- `output/sessions/<data_hora>/`: CSV de debug, snapshot de configuração, Excel, vídeo anotado e frames de gaps, gerados em runtime.
- `dashboard/data/`: frame e estado do programa para o stream FastAPI, gerados em runtime.
- InfluxDB: métricas live usadas pelo Grafana.
- Grafana: dashboard do operador provisionado em `../../grafana/provisioning`.
