from datetime import date

import pandas as pd

from .metricas import peso_tarefa
from .modelos import Projeto


def _distribuir(serie: pd.Series, inicio: date | None, fim: date | None, valor_total: float) -> None:
    if inicio is None or fim is None or valor_total == 0:
        return
    if fim < inicio:
        inicio, fim = fim, inicio
    dias = (fim - inicio).days + 1
    valor_diario = valor_total / dias
    inicio_clip = max(inicio, serie.index[0].date())
    fim_clip = min(fim, serie.index[-1].date())
    if fim_clip < inicio_clip:
        return
    idx = pd.date_range(inicio_clip, fim_clip, freq="D")
    serie.loc[idx] += valor_diario


def gerar_curva_s(
    projeto: Projeto,
    data_status: date | None = None,
    percentual_concluido_alvo: float | None = None,
) -> pd.DataFrame:
    """Retorna um DataFrame diário com as colunas 'Linha de Base', 'Cronograma Atual' e 'Realizado' (acumulados).

    'Linha de Base' distribui o peso de cada tarefa (custo ou duração planejada) entre
    Início/Término da linha de base. 'Cronograma Atual' distribui o mesmo peso entre o
    Início/Término vigente (que reflete atrasos e replanejamentos). 'Realizado' distribui
    o peso já concluído (peso x % concluído) entre o início real e a data de status.

    Se 'percentual_concluido_alvo' for informado (ex.: o % Concluído nativo do MS Project),
    a curva 'Realizado' é recalibrada para que seu valor na data de status bata exatamente
    com esse percentual, preservando o formato da curva ao longo do tempo.
    """
    tarefas = projeto.tarefas_detalhe
    if data_status is None:
        data_status = projeto.data_status or date.today()

    usa_custo = projeto.tem_custo

    datas_relevantes = []
    for t in tarefas:
        datas_relevantes += [
            t.inicio_linha_base,
            t.termino_linha_base,
            t.inicio,
            t.termino,
        ]
    datas_relevantes = [d for d in datas_relevantes if d is not None]
    datas_relevantes.append(data_status)

    if not datas_relevantes:
        hoje = date.today()
        datas_relevantes = [hoje, hoje]

    data_min = min(datas_relevantes)
    data_max = max(datas_relevantes)
    indice = pd.date_range(data_min, data_max, freq="D")

    linha_base_diario = pd.Series(0.0, index=indice)
    atual_diario = pd.Series(0.0, index=indice)
    realizado_diario = pd.Series(0.0, index=indice)

    for t in tarefas:
        peso = peso_tarefa(t, usa_custo)
        _distribuir(linha_base_diario, t.inicio_linha_base, t.termino_linha_base, peso)
        _distribuir(atual_diario, t.inicio, t.termino, peso)

        valor_realizado = peso * (t.percentual_concluido / 100)
        inicio_realizado = t.inicio_real or t.inicio
        fim_realizado = t.termino_real or (min(t.termino, data_status) if t.termino else data_status)
        _distribuir(realizado_diario, inicio_realizado, fim_realizado, valor_realizado)

    linha_base_acumulada = linha_base_diario.cumsum()
    atual_acumulado = atual_diario.cumsum()
    realizado_acumulado = realizado_diario.cumsum()

    data_status_clip = pd.Timestamp(min(max(data_status, indice[0].date()), indice[-1].date()))

    total_linha_base = linha_base_acumulada.iloc[-1] if len(linha_base_acumulada) else 0.0
    if percentual_concluido_alvo is not None and total_linha_base > 0:
        pct_bruto_hoje = realizado_acumulado.loc[data_status_clip] / total_linha_base * 100
        if pct_bruto_hoje > 0:
            fator = percentual_concluido_alvo / pct_bruto_hoje
            realizado_acumulado = realizado_acumulado * fator

    # Curva combinada: usa o Realizado até a data de status e, a partir daí, projeta o
    # restante seguindo o ritmo (formato) do Cronograma Atual, reescalado para terminar
    # exatamente em 100% (total da linha de base) em vez de gerar descontinuidade ou
    # ultrapassar o total do projeto.
    valor_realizado_hoje = realizado_acumulado.loc[data_status_clip]
    valor_atual_hoje = atual_acumulado.loc[data_status_clip]
    executado_previsto = realizado_acumulado.copy()
    futuro = executado_previsto.index > data_status_clip

    formato_restante = atual_acumulado[futuro] - valor_atual_hoje
    crescimento_restante_atual = atual_acumulado.iloc[-1] - valor_atual_hoje
    falta_para_100 = total_linha_base - valor_realizado_hoje

    if crescimento_restante_atual > 0:
        escala = falta_para_100 / crescimento_restante_atual
        executado_previsto[futuro] = valor_realizado_hoje + formato_restante * escala
    else:
        executado_previsto[futuro] = valor_realizado_hoje

    df = pd.DataFrame(
        {
            "Linha de Base": linha_base_acumulada,
            "Cronograma Atual": atual_acumulado,
            "Realizado": realizado_acumulado,
            "Realizado / Previsto": executado_previsto,
        }
    )
    df.index.name = "Data"
    return df
