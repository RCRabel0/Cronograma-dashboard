from datetime import date

import pytest

from cronograma.metricas import calcular_indicadores, gerar_percepcoes, peso_tarefa

DATA_STATUS = date(2026, 7, 24)


def test_unidade_por_metodo(projeto_com_custo, projeto_sem_custo):
    assert calcular_indicadores(projeto_com_custo, DATA_STATUS).unidade == "R$"
    assert calcular_indicadores(projeto_sem_custo, DATA_STATUS).unidade == "h"
    assert calcular_indicadores(projeto_com_custo, DATA_STATUS, metodo_peso="duracao").unidade == "h"


def test_peso_tarefa_metodos(projeto_com_peso):
    tarefa_a = next(t for t in projeto_com_peso.tarefas_detalhe if t.nome == "Tarefa A")
    assert peso_tarefa(tarefa_a, "duracao", tem_custo=False) == 160.0
    assert peso_tarefa(tarefa_a, "peso_editado", tem_custo=False) == 80.0


def test_peso_editado_com_fallback(projeto_com_custo):
    # Sem valor de peso preenchido, 'peso_editado' cai para custo (projeto tem custo).
    tarefa = projeto_com_custo.tarefas_detalhe[0]
    assert tarefa.peso_editado is None
    assert peso_tarefa(tarefa, "peso_editado", tem_custo=True) == tarefa.custo_linha_base


def test_indicadores_com_peso_editado(projeto_com_peso):
    data_status = date(2026, 2, 15)
    padrao = calcular_indicadores(projeto_com_peso, data_status)
    com_peso = calcular_indicadores(projeto_com_peso, data_status, metodo_peso="peso_editado")
    # Tarefa A (100% concluída) vale 80/100 no método de peso, mas só 160/800 por duração.
    assert com_peso.ev_total == pytest.approx(80.0)
    assert padrao.ev_total == pytest.approx(160.0)
    assert com_peso.spi != padrao.spi


def test_spi_cpi_calculados(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    assert ind.spi is not None and 0 < ind.spi < 2
    assert ind.cpi is not None and 0 < ind.cpi < 2
    assert ind.total_tarefas == 5
    assert ind.tarefas_atrasadas > 0


def test_percepcoes_categorias(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    percepcoes = gerar_percepcoes(projeto_com_custo, ind, idioma="pt")
    assert percepcoes
    categorias = {c for c, _ in percepcoes}
    assert categorias <= {"alerta", "sucesso", "info"}


def test_percepcoes_ingles(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    percepcoes_en = gerar_percepcoes(projeto_com_custo, ind, idioma="en")
    textos = " ".join(texto for _, texto in percepcoes_en)
    assert "project" in textos.lower()
