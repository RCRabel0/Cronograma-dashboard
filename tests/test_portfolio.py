import pytest

from cronograma.portfolio import (
    calcular_indicadores_portfolio,
    gerar_curva_s_portfolio,
    indicadores_consolidados,
    pesos_relativos,
    tabela_comparativa,
)


@pytest.fixture()
def projetos(projeto_com_custo, projeto_sem_custo):
    return {"a.xml": projeto_com_custo, "b.xml": projeto_sem_custo}


def test_indicadores_por_projeto(projetos):
    ind = calcular_indicadores_portfolio(projetos)
    assert set(ind) == {"a.xml", "b.xml"}
    assert ind["a.xml"].unidade == "R$"
    assert ind["b.xml"].unidade == "h"


def test_tabela_comparativa(projetos):
    ind = calcular_indicadores_portfolio(projetos)
    tabela = tabela_comparativa(projetos, ind, idioma="pt")
    assert len(tabela) == 2
    assert "Projeto" in tabela.columns
    assert "Linha de Base Ativa" in tabela.columns


def test_consolidado(projetos):
    ind = calcular_indicadores_portfolio(projetos)
    consolidado = indicadores_consolidados(projetos, ind)
    assert consolidado["total_projetos"] == 2
    assert 0 <= consolidado["percentual_concluido"] <= 100
    assert consolidado["total_tarefas"] == ind["a.xml"].total_tarefas + ind["b.xml"].total_tarefas


def test_pesos_relativos_somam_100(projetos):
    pesos = pesos_relativos(projetos)
    assert sum(pesos.values()) == pytest.approx(100.0)


def test_curva_portfolio_em_percentual(projetos):
    ind = calcular_indicadores_portfolio(projetos)
    curva = gerar_curva_s_portfolio(projetos, ind)
    assert not curva.empty
    assert set(curva.columns) == {"Linha de Base", "Realizado / Previsto"}
    # Curva consolidada é em % — nunca deve passar (muito) de 100.
    assert curva["Linha de Base"].max() == pytest.approx(100.0, abs=0.5)


def test_metodo_peso_propagado(projetos, projeto_com_peso):
    projetos_com_peso = dict(projetos, **{"c.xml": projeto_com_peso})
    ind_padrao = calcular_indicadores_portfolio(projetos_com_peso)
    ind_peso = calcular_indicadores_portfolio(projetos_com_peso, metodo_peso="peso_editado")
    # Só o projeto com coluna de peso muda; os demais usam o fallback e ficam iguais.
    assert ind_peso["c.xml"].ev_total != ind_padrao["c.xml"].ev_total
    assert ind_peso["a.xml"].ev_total == ind_padrao["a.xml"].ev_total
