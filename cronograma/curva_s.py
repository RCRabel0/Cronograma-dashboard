from collections import defaultdict
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
    metodo_peso: str | None = None,
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

    tem_custo = projeto.tem_custo
    if metodo_peso is None:
        metodo_peso = "custo" if tem_custo else "duracao"

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
        peso = peso_tarefa(t, metodo_peso, tem_custo)
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


def _distribuir_por_mes(
    inicio: date | None, fim: date | None, valor_total: float, meses: pd.PeriodIndex,
) -> dict:
    """Distribui 'valor_total' proporcionalmente aos dias de cada mês dentro de
    [inicio, fim] — a mesma premissa de distribuição uniforme por dia usada em
    '_distribuir', só que agregada por mês em vez de acumulada por dia."""
    resultado: dict = {}
    if inicio is None or fim is None or valor_total == 0:
        return resultado
    if fim < inicio:
        inicio, fim = fim, inicio
    dias_totais = (fim - inicio).days + 1
    if dias_totais <= 0:
        return resultado
    valor_diario = valor_total / dias_totais
    for mes in meses:
        inicio_mes = mes.start_time.date()
        fim_mes = mes.end_time.date()
        overlap_inicio = max(inicio, inicio_mes)
        overlap_fim = min(fim, fim_mes)
        dias_no_mes = (overlap_fim - overlap_inicio).days + 1
        if dias_no_mes > 0:
            resultado[mes] = valor_diario * dias_no_mes
    return resultado


def _calcular_wbs(tarefas_todas: list) -> dict:
    """Gera a numeração WBS (1, 1.1, 1.1.1, 1.1.1.1...) por posição na estrutura de
    tópicos (nivel_esquema), na ordem em que as tarefas aparecem no arquivo — o mesmo
    algoritmo que o MS Project usa para numerar automaticamente. Não há limite de
    profundidade aqui: quem controla até que nível aparece na tabela é o filtro por
    nível em 'gerar_tabela_fisico_financeiro'."""
    contadores: list[int] = []
    wbs_por_uid: dict = {}
    for t in tarefas_todas:
        nivel = max(t.nivel_esquema, 1)
        if nivel > len(contadores):
            contadores.extend([0] * (nivel - len(contadores)))
        else:
            contadores = contadores[:nivel]
        contadores[nivel - 1] += 1
        wbs_por_uid[t.uid] = ".".join(str(c) for c in contadores)
    return wbs_por_uid


def _construir_pais(tarefas_todas: list) -> dict:
    """Mapeia uid -> uid da tarefa-pai imediata na estrutura de tópicos, a partir do
    nivel_esquema e da ordem do arquivo (mesma lógica de pilha usada em '_calcular_wbs').
    Tarefas de nível 1 (ou sem pai visível) mapeiam para None."""
    pilha: list[tuple] = []
    pai_por_uid: dict = {}
    for t in tarefas_todas:
        nivel = max(t.nivel_esquema, 1)
        while pilha and pilha[-1][0] >= nivel:
            pilha.pop()
        pai_por_uid[t.uid] = pilha[-1][1] if pilha else None
        pilha.append((nivel, t.uid))
    return pai_por_uid


def gerar_tabela_fisico_financeiro(
    projeto: Projeto,
    data_status: date | None = None,
    metodo_peso: str | None = None,
    nivel_maximo_wbs: int = 4,
) -> pd.DataFrame:
    """Monta o cronograma físico-financeiro clássico: uma linha 'Planejado' e uma linha
    'Realizado' por tarefa, com o % do peso de cada tarefa alocado em cada mês do
    cronograma — o formato de planilha (tarefas x meses) usado em obras/EPC, com o
    período de execução marcado mês a mês em vez de um gráfico de barras.

    'nivel_maximo_wbs' mostra a hierarquia de forma acumulada: ao escolher o nível N,
    aparecem as tarefas de resumo (fases/grupos) e de detalhe de TODOS os níveis de 1
    até N — cada tarefa de resumo com peso, % concluído e distribuição mensal agregados
    (somados) a partir de todas as suas tarefas-filha, não apenas as diretas, do mesmo
    jeito que uma planilha físico-financeira tradicional mostra tanto o total da fase
    quanto o detalhe de cada atividade. Tarefas mais profundas que N ficam representadas
    pelo resumo ancestral visível, sem serem exibidas como linha própria.

    O peso de cada tarefa é normalizado para % do peso total do cronograma (sempre
    calculado só a partir das tarefas de detalhe, para não contar duas vezes o peso já
    somado nos resumos). A coluna 'WBS' numera a hierarquia completa na mesma ordem do
    arquivo original. As colunas 'Crítica' e 'Atrasada' também são agregadas (verdadeiro
    se qualquer tarefa-filha for crítica/atrasada), para filtros e colorização na UI.
    """
    tarefas_detalhe = projeto.tarefas_detalhe
    if data_status is None:
        data_status = projeto.data_status or date.today()

    tem_custo = projeto.tem_custo
    if metodo_peso is None:
        metodo_peso = "custo" if tem_custo else "duracao"

    peso_total = sum(peso_tarefa(t, metodo_peso, tem_custo) for t in tarefas_detalhe) or 1.0

    datas_relevantes = []
    for t in tarefas_detalhe:
        datas_relevantes += [t.inicio_linha_base, t.termino_linha_base, t.inicio, t.termino]
    datas_relevantes = [d for d in datas_relevantes if d is not None]
    if not datas_relevantes:
        return pd.DataFrame()

    meses = pd.period_range(min(datas_relevantes), max(datas_relevantes), freq="M")

    wbs_por_uid = _calcular_wbs(projeto.tarefas)
    pai_por_uid = _construir_pais(projeto.tarefas)

    peso_agregado: dict = defaultdict(float)
    planejado_agregado: dict = defaultdict(lambda: defaultdict(float))
    realizado_agregado: dict = defaultdict(lambda: defaultdict(float))
    critica_agregada: dict = defaultdict(bool)
    atrasada_agregada: dict = defaultdict(bool)

    for t in tarefas_detalhe:
        peso_pct = peso_tarefa(t, metodo_peso, tem_custo) / peso_total * 100

        planejado_mensal = _distribuir_por_mes(
            t.inicio_linha_base or t.inicio, t.termino_linha_base or t.termino, peso_pct, meses,
        )
        valor_realizado = peso_pct * (t.percentual_concluido / 100)
        inicio_realizado = t.inicio_real or t.inicio
        fim_realizado = t.termino_real or (min(t.termino, data_status) if t.termino else data_status)
        realizado_mensal = _distribuir_por_mes(inicio_realizado, fim_realizado, valor_realizado, meses)

        # Soma a contribuição da tarefa em si e em toda a cadeia de ancestrais (pai,
        # avô...), para que cada resumo visível carregue o total de todas as suas
        # tarefas-filha, não só as diretas.
        uid = t.uid
        while uid is not None:
            peso_agregado[uid] += peso_pct
            for mes, valor in planejado_mensal.items():
                planejado_agregado[uid][mes] += valor
            for mes, valor in realizado_mensal.items():
                realizado_agregado[uid][mes] += valor
            critica_agregada[uid] = critica_agregada[uid] or t.critica
            atrasada_agregada[uid] = atrasada_agregada[uid] or t.atrasada
            uid = pai_por_uid.get(uid)

    tarefas_visiveis = [t for t in projeto.tarefas if 1 <= t.nivel_esquema <= nivel_maximo_wbs]

    linhas = []
    for t in tarefas_visiveis:
        peso_pct = peso_agregado.get(t.uid, 0.0)
        planejado_mensal = planejado_agregado.get(t.uid, {})
        realizado_mensal = realizado_agregado.get(t.uid, {})
        realizado_total = sum(realizado_mensal.values())
        pct_concluido = (realizado_total / peso_pct * 100) if peso_pct > 0 else 0.0

        for rotulo, valores_mes in (("Planejado", planejado_mensal), ("Realizado", realizado_mensal)):
            linha = {
                "WBS": wbs_por_uid.get(t.uid, ""),
                "Tarefa": t.nome,
                "Crítica": critica_agregada.get(t.uid, False),
                "Atrasada": atrasada_agregada.get(t.uid, False),
                "Percentual Concluído": pct_concluido,
                "Linha": rotulo,
                "Peso (%)": peso_pct,
            }
            for mes in meses:
                # Usa NaN (não None) para célula sem alocação — garante que a coluna
                # inteira fique float64 mesmo quando nenhuma tarefa tem valor naquele
                # mês, o que faz o NumberColumn do Streamlit exibir a célula em branco
                # em vez do texto literal "None".
                linha[mes.strftime("%b/%y")] = valores_mes.get(mes) or float("nan")
            linhas.append(linha)

    return pd.DataFrame(linhas)
