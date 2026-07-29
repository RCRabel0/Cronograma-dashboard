from datetime import date

import pytest

from cronograma.curva_s import gerar_curva_s
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
