"""Consolidação de múltiplos cronogramas em uma visão de portfólio."""

from datetime import date

import pandas as pd

from .curva_s import gerar_curva_s
from .i18n import formatar_data, t, tf
from .metricas import Indicadores, calcular_indicadores
from .modelos import Projeto


def data_status_projeto(projeto: Projeto) -> date:
    return projeto.data_status or date.today()


def calcular_indicadores_portfolio(projetos: dict[str, Projeto]) -> dict[str, Indicadores]:
    """Calcula os indicadores de cada projeto usando a própria data de status do arquivo."""
    return {nome: calcular_indicadores(projeto, data_status_projeto(projeto)) for nome, projeto in projetos.items()}


def _peso_projeto(projeto: Projeto) -> float:
    """Tamanho do projeto usado para ponderar a consolidação do portfólio. Usa a duração
    (linha de base, em horas) das tarefas de detalhe — métrica sempre disponível e
    comparável entre projetos, mesmo quando só alguns têm custo preenchido."""
    tarefas = projeto.tarefas_detalhe
    peso = sum(t.duracao_linha_base_horas or t.duracao_horas for t in tarefas)
    return peso if peso > 0 else 1.0


def pesos_relativos(projetos: dict[str, Projeto]) -> dict[str, float]:
    """Peso relativo (%) de cada projeto na consolidação do portfólio (indicadores e Curva
    S), baseado na duração total de linha de base (ou atual) das tarefas de detalhe."""
    pesos = {nome: _peso_projeto(projeto) for nome, projeto in projetos.items()}
    total = sum(pesos.values()) or 1.0
    return {nome: peso / total * 100 for nome, peso in pesos.items()}


def periodo_linha_base_ativa(projeto: Projeto, idioma: str) -> str:
    """Data em que a linha de base ativa foi salva, quando o arquivo traz essa
    informação (normalmente só em .mpp nativo); senão, cai para o período
    planejado (início-término) da linha de base, que sempre está disponível."""
    if projeto.data_salva_linha_base:
        return formatar_data(projeto.data_salva_linha_base, idioma)
    resumo = projeto.tarefa_resumo_projeto
    inicio_lb = resumo.inicio_linha_base if resumo else None
    termino_lb = resumo.termino_linha_base if resumo else None
    if not inicio_lb and not termino_lb:
        return t("N/D", idioma)
    return tf(
        "{inicio} a {termino}", idioma,
        inicio=formatar_data(inicio_lb, idioma) if inicio_lb else t("N/D", idioma),
        termino=formatar_data(termino_lb, idioma) if termino_lb else t("N/D", idioma),
    )


def tabela_comparativa(projetos: dict[str, Projeto], indicadores_por_projeto: dict[str, Indicadores], idioma: str = "pt") -> pd.DataFrame:
    linhas = []
    for nome, projeto in projetos.items():
        ind = indicadores_por_projeto[nome]
        linhas.append(
            {
                t("Projeto", idioma): projeto.nome,
                t("Início", idioma): formatar_data(projeto.inicio, idioma) if projeto.inicio else t("N/D", idioma),
                t("Término", idioma): formatar_data(projeto.termino, idioma) if projeto.termino else t("N/D", idioma),
                t("Data de status", idioma): formatar_data(data_status_projeto(projeto), idioma),
                t("Linha de Base Ativa", idioma): periodo_linha_base_ativa(projeto, idioma),
                t("% Concluído", idioma): round(ind.percentual_concluido, 1),
                "SPI": round(ind.spi, 2) if ind.spi is not None else None,
                "CPI": round(ind.cpi, 2) if ind.cpi is not None else None,
                t("Atraso (dias)", idioma): ind.atraso_dias,
                t("Tarefas Atrasadas", idioma): ind.tarefas_atrasadas,
                t("Tarefas Críticas Atrasadas", idioma): ind.tarefas_criticas_atrasadas,
                t("Total de Tarefas", idioma): ind.total_tarefas,
            }
        )
    return pd.DataFrame(linhas)


def indicadores_consolidados(projetos: dict[str, Projeto], indicadores_por_projeto: dict[str, Indicadores]) -> dict:
    pesos = {nome: _peso_projeto(projeto) for nome, projeto in projetos.items()}
    peso_total = sum(pesos.values()) or 1.0

    percentual_consolidado = sum(ind.percentual_concluido * pesos[nome] for nome, ind in indicadores_por_projeto.items()) / peso_total

    spis = [(ind.spi, pesos[nome]) for nome, ind in indicadores_por_projeto.items() if ind.spi is not None]
    spi_consolidado = sum(v * p for v, p in spis) / sum(p for _, p in spis) if spis else None

    cpis = [(ind.cpi, pesos[nome]) for nome, ind in indicadores_por_projeto.items() if ind.cpi is not None]
    cpi_consolidado = sum(v * p for v, p in cpis) / sum(p for _, p in cpis) if cpis else None

    return {
        "total_projetos": len(projetos),
        "projetos_atrasados": sum(1 for ind in indicadores_por_projeto.values() if ind.atraso_dias > 0),
        "percentual_concluido": percentual_consolidado,
        "spi": spi_consolidado,
        "cpi": cpi_consolidado,
        "tarefas_atrasadas": sum(ind.tarefas_atrasadas for ind in indicadores_por_projeto.values()),
        "tarefas_criticas_atrasadas": sum(ind.tarefas_criticas_atrasadas for ind in indicadores_por_projeto.values()),
        "total_tarefas": sum(ind.total_tarefas for ind in indicadores_por_projeto.values()),
    }


def gerar_curva_s_portfolio(projetos: dict[str, Projeto], indicadores_por_projeto: dict[str, Indicadores]) -> pd.DataFrame:
    """Consolida a Curva S de todos os projetos numa única curva, em % do valor total
    de cada projeto (para poder somar cronogramas com unidades diferentes, ex.: alguns
    em custo e outros em horas), ponderada pelo tamanho (duração) de cada projeto."""
    pesos = {nome: _peso_projeto(projeto) for nome, projeto in projetos.items()}
    curvas_pct: dict[str, pd.DataFrame] = {}

    for nome, projeto in projetos.items():
        ind = indicadores_por_projeto[nome]
        curva = gerar_curva_s(projeto, data_status_projeto(projeto), percentual_concluido_alvo=ind.percentual_concluido)
        total = curva["Linha de Base"].max()
        if total <= 0 or curva.empty:
            continue
        curvas_pct[nome] = pd.DataFrame(
            {
                "Linha de Base": curva["Linha de Base"] / total * 100,
                "Realizado / Previsto": curva["Realizado / Previsto"] / total * 100,
            }
        )

    if not curvas_pct:
        return pd.DataFrame(columns=["Linha de Base", "Realizado / Previsto"])

    data_min = min(c.index.min() for c in curvas_pct.values())
    data_max = max(c.index.max() for c in curvas_pct.values())
    eixo = pd.date_range(data_min, data_max, freq="D")

    peso_total = sum(pesos[nome] for nome in curvas_pct) or 1.0
    consolidado = pd.DataFrame(0.0, index=eixo, columns=["Linha de Base", "Realizado / Previsto"])
    for nome, curva_pct in curvas_pct.items():
        # Fora do intervalo do próprio projeto: antes do início conta como 0%,
        # depois do fim mantém o último valor (que a Curva S já calibra para 100%).
        reindexado = curva_pct.reindex(eixo).ffill().fillna(0.0)
        peso_relativo = pesos[nome] / peso_total
        consolidado["Linha de Base"] += reindexado["Linha de Base"] * peso_relativo
        consolidado["Realizado / Previsto"] += reindexado["Realizado / Previsto"] * peso_relativo

    return consolidado
