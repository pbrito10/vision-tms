# Vision TMS - mapa atual

Este backend corre como API FastAPI e comunica com o frontend React, InfluxDB e Grafana.
O fluxo antigo de menu Python/Streamlit foi removido.

## Entrada da API

- `api/main.py`: cria a aplicação FastAPI.
- `api/routes.py`: expõe saúde, estado, câmara, programa e configuração de bancadas.
- `api/services.py`: casos de uso da aplicação, persistência de YAML/JSON e gestão dos processos.
- `process_entrypoints.py`: entrypoints limpos para os subprocessos do pipeline.

## Pipeline de visão

- `capture_process.py`: captura frames da câmara.
- `detection_process.py`: deteta mãos nos frames.
- `monitor_process.py`: classifica zonas, controla o ciclo, publica imagem/estado e escreve métricas.

## Configuração

- `config/settings.yaml`: parâmetros técnicos editados no código/YAML.
- `config/benches.json`: bancadas guardadas pelo frontend.
- `config/rois.json`: ROIs ativas geradas a partir da bancada escolhida.

## Saídas

- `output/`: CSV de debug e Excel de sessão, gerados em runtime.
- `dashboard/data/`: frame e estado do programa para o stream FastAPI, gerados em runtime.
- InfluxDB: métricas live usadas pelo Grafana.
- Grafana: dashboard do operador provisionado em `../../grafana/provisioning`.
