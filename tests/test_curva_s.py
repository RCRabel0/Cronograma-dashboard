from datetime import date

import pytest

from cronograma.curva_s import gerar_curva_s, gerar_tabela_fisico_financeiro
from cronograma.metricas import calcular_indicadores

DATA_STATUS = date(2026, 7, 24)
COLUNAS = {"Linha de Base", "Cronograma Atual", "Realizado", "Realizado / Previsto"}


def test_colunas_e_monotonia(projeto_com_custo):
    curva = gerar_curva_s(projeto_com_custo, DATA_STATUS)
    assert set(curva.columns) == COLUNAS
    assert (curva["Linha de Base"].diff().dropna() >= -1e-9).all()


def test_total_linha_base_igual_orcamento(projeto_com_custo):
    curva = gerar_curva_s(projeto_com_custo, DATA_STATUS)
    total_custo = sum(t.custo_linha_base for t in projeto_com_custo.tarefas_detalhe)
    assert curva["Linha de Base"].max() == pytest.approx(total_custo, rel=1e-6)


def test_calibracao_percentual(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    curva = gerar_curva_s(projeto_com_custo, DATA_STATUS, percentual_concluido_alvo=ind.percentual_concluido)
    import pandas as pd

    total = curva["Linha de Base"].max()
    pct_na_data = curva.loc[pd.Timestamp(DATA_STATUS), "Realizado"] / total * 100
    assert pct_na_data == pytest.approx(ind.percentual_concluido, abs=0.5)


def test_curva_termina_em_100(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    curva = gerar_curva_s(projeto_com_custo, DATA_STATUS, percentual_concluido_alvo=ind.percentual_concluido)
    total = curva["Linha de Base"].max()
    assert curva["Realizado / Previsto"].iloc[-1] == pytest.approx(total, rel=1e-6)


def test_metodo_peso_editado_muda_total(projeto_com_peso):
    data_status = date(2026, 2, 15)
    curva_padrao = gerar_curva_s(projeto_com_peso, data_status)
    curva_peso = gerar_curva_s(projeto_com_peso, data_status, metodo_peso="peso_editado")
    assert curva_padrao["Linha de Base"].max() == pytest.approx(800.0)
    assert curva_peso["Linha de Base"].max() == pytest.approx(100.0)


def test_ff_estrutura_e_colunas(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    assert {"Tarefa", "Crítica", "Linha", "Peso (%)"} <= set(df.columns)
    assert set(df["Linha"].unique()) == {"Planejado", "Realizado"}
    # Duas linhas (Planejado + Realizado) por tarefa de detalhe.
    assert len(df) == 2 * len(projeto_com_custo.tarefas_detalhe)


def test_ff_peso_soma_100(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    peso_por_tarefa = df[df["Linha"] == "Planejado"]["Peso (%)"]
    assert peso_por_tarefa.sum() == pytest.approx(100.0, rel=1e-6)


def test_ff_planejado_soma_bate_peso_da_tarefa(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    colunas_mes = [c for c in df.columns if c not in ("Tarefa", "Crítica", "Linha", "Peso (%)")]
    planejado = df[df["Linha"] == "Planejado"]
    for _, linha in planejado.iterrows():
        soma_meses = sum(v for v in (linha[c] for c in colunas_mes) if v is not None and v == v)
        assert soma_meses == pytest.approx(linha["Peso (%)"], abs=0.05)


def test_ff_realizado_reflete_percentual_concluido(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    colunas_mes = [c for c in df.columns if c not in ("Tarefa", "Crítica", "Linha", "Peso (%)")]
    tarefas_por_nome = {t.nome: t for t in projeto_com_custo.tarefas_detalhe}
    realizado = df[df["Linha"] == "Realizado"]
    for _, linha in realizado.iterrows():
        tarefa = tarefas_por_nome[linha["Tarefa"]]
        soma_meses = sum(v for v in (linha[c] for c in colunas_mes) if v is not None and v == v)
        esperado = linha["Peso (%)"] * (tarefa.percentual_concluido / 100)
        assert soma_meses == pytest.approx(esperado, abs=0.05)


def test_ff_projeto_sem_datas_retorna_vazio():
    from cronograma.modelos import Projeto, Tarefa

    tarefa_sem_data = Tarefa(uid="1", id=1, nome="Sem data")
    projeto = Projeto(nome="Vazio", tarefas=[tarefa_sem_data])
    df = gerar_tabela_fisico_financeiro(projeto, DATA_STATUS)
    assert df.empty
