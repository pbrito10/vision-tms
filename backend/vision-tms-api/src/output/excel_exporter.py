from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill

from src.output.metrics_snapshot import MetricsSnapshot
from src.output.output_interface import OutputInterface
from src.tracking.cycle_result import CycleResult
from src.tracking.task_event import TaskEvent

# Cor de destaque para a zona gargalo (amarelo-âmbar)
_BOTTLENECK_FILL = PatternFill(start_color="FFD966", end_color="FFD966", fill_type="solid")
_HEADER_FONT     = Font(bold=True)

# Mapeamento direto para evitar ternário aninhado em _write_cycles
_ORDER_LABEL: dict[bool | None, str] = {True: "Sim", False: "Não", None: "—"}


class ExcelExporter(OutputInterface):
    """Exporta os dados da sessão para um ficheiro .xlsx no fim da sessão.

    Gera quatro folhas: Resumo, Métricas por Zona, Ciclos e Eventos.
    A zona gargalo é destacada a amarelo na folha de métricas.

    write() é chamado uma vez no fim da sessão.
    """

    def __init__(self, output_dir: Path, session_start: datetime) -> None:
        self._output_dir    = output_dir
        self._session_start = session_start
        self._events:       list[TaskEvent]  = []
        self._cycle_order:  dict[int, bool]  = {}  # cycle_number → sequence_in_order

        output_dir.mkdir(parents=True, exist_ok=True)

    def add_event(self, event: TaskEvent) -> None:
        """Acumula TaskEvents durante a sessão para exportar no fim."""
        self._events.append(event)

    def add_cycle_result(self, cycle_result: CycleResult) -> None:
        """Regista se as zonas do ciclo foram visitadas na sequência correta."""
        self._cycle_order[cycle_result.cycle_number] = cycle_result.sequence_in_order

    def write(self, snapshot: MetricsSnapshot) -> None:
        """Gera o ficheiro Excel com todas as folhas."""
        filename = f"sessao_{self._session_start.strftime('%Y-%m-%d_%Hh%M')}.xlsx"
        path     = self._output_dir / filename

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            self._write_summary(writer, snapshot)
            self._write_zone_metrics(writer, snapshot)
            self._write_cycles(writer)
            self._write_events(writer)

    # ── Folhas ───────────────────────────────────────────────────────────────

    def _write_summary(self, writer: pd.ExcelWriter, snapshot: MetricsSnapshot) -> None:
        """Folha 'Resumo': métricas globais da sessão numa única tabela de dois campos."""
        cycle   = snapshot.cycle_metrics
        avg_s   = "—"
        std_s   = "—"
        if cycle.count():
            avg_s = round(cycle.average().total_seconds(), 2)
            std_s = round(cycle.std_deviation().total_seconds(), 2)

        rows = [
            ("Data",                    self._session_start.strftime("%Y-%m-%d %H:%M")),
            ("Duração total (s)",       round(snapshot.session_duration.total_seconds(), 1)),
            ("Ciclos completos",        cycle.count()),
            ("Tempo médio ciclo (s)",   avg_s),
            ("Desvio padrão ciclo (s)", std_s),
            ("% Tempo produtivo",       round(snapshot.productive_percentage, 1)),
            ("% Tempo transição",       round(snapshot.transition_percentage, 1)),
            ("% Tempo interrupção",     round(snapshot.interruption_percentage, 1)),
            ("Zona gargalo",            snapshot.bottleneck_zone or "—"),
        ]

        df = pd.DataFrame(rows, columns=["Métrica", "Valor"])
        df.to_excel(writer, sheet_name="Resumo", index=False)
        self._bold_headers(writer, "Resumo", df)

    def _write_zone_metrics(self, writer: pd.ExcelWriter, snapshot: MetricsSnapshot) -> None:
        """Folha 'Métricas por Zona': estatísticas por zona com gargalo destacado a amarelo."""
        rows = []
        for zone_name, metrics in snapshot.task_metrics.items():
            if metrics.count() == 0:
                continue
            rows.append({
                "Zona":            zone_name,
                "Mínimo (s)":      round(metrics.minimum().total_seconds(), 3),
                "Médio (s)":       round(metrics.average().total_seconds(), 3),
                "Máximo (s)":      round(metrics.maximum().total_seconds(), 3),
                "Desvio Padrão (s)": round(metrics.std_deviation().total_seconds(), 3),
                "Ocorrências":     metrics.count(),
            })

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Métricas por Zona", index=False)
        self._bold_headers(writer, "Métricas por Zona", df)
        self._highlight_bottleneck(writer, "Métricas por Zona", df, snapshot.bottleneck_zone)

    def _write_cycles(self, writer: pd.ExcelWriter) -> None:
        """Folha 'Ciclos': uma linha por ciclo com início, fim, duração e sequência correta.

        O início e fim de cada ciclo são reconstruídos aqui a partir dos TaskEvents
        acumulados, porque o CycleResult apenas guarda duração, não timestamps absolutos.
        """
        cycles: dict[int, list[TaskEvent]] = {}
        for event in self._events:
            cycles.setdefault(event.cycle_number, []).append(event)

        rows = []
        for cycle_number, events in sorted(cycles.items()):
            sequence_in_order = self._cycle_order.get(cycle_number, None)
            start    = min(e.start_time for e in events)
            end      = max(e.end_time   for e in events)
            duration = round((end - start).total_seconds(), 2)
            rows.append({
                "Nº Ciclo":           cycle_number,
                "Início":             start.strftime("%H:%M:%S"),
                "Fim":                end.strftime("%H:%M:%S"),
                "Duração (s)":        duration,
                "Sequência Correta":  _ORDER_LABEL.get(sequence_in_order, "—"),
            })

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Ciclos", index=False)
        self._bold_headers(writer, "Ciclos", df)

    def _write_events(self, writer: pd.ExcelWriter) -> None:
        """Folha 'Eventos': uma linha por TaskEvent, incluindo tarefas forçadas por timeout."""
        rows = [
            {
                "Ciclo":       event.cycle_number,
                "Zona":        event.zone_name,
                "Início":      event.start_time.strftime("%H:%M:%S.%f")[:-3],
                "Fim":         event.end_time.strftime("%H:%M:%S.%f")[:-3],
                "Duração (s)": round(event.duration.total_seconds(), 3),
                "Forçado":     _ORDER_LABEL[event.was_forced],
            }
            for event in self._events
        ]

        df = pd.DataFrame(rows)
        df.to_excel(writer, sheet_name="Eventos", index=False)
        self._bold_headers(writer, "Eventos", df)

    # ── Formatação ────────────────────────────────────────────────────────────

    def _bold_headers(self, writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame) -> None:
        """Aplica bold à linha de cabeçalho da folha indicada."""
        sheet = writer.sheets[sheet_name]
        for col_idx in range(1, len(df.columns) + 1):
            sheet.cell(row=1, column=col_idx).font = _HEADER_FONT

    def _highlight_bottleneck(
        self,
        writer: pd.ExcelWriter,
        sheet_name: str,
        df: pd.DataFrame,
        bottleneck: str | None,
    ) -> None:
        """Destaca a amarelo todas as células da linha correspondente à zona gargalo."""
        if bottleneck is None or "Zona" not in df.columns:
            return

        sheet    = writer.sheets[sheet_name]
        num_cols = len(df.columns)

        # Linha 1 é o cabeçalho — dados começam na linha 2
        for row_idx, zone_name in enumerate(df["Zona"], start=2):
            if zone_name == bottleneck:
                for col_idx in range(1, num_cols + 1):
                    sheet.cell(row=row_idx, column=col_idx).fill = _BOTTLENECK_FILL
