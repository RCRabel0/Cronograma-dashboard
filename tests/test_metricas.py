from datetime import date

import pytest

from cronograma.metricas import (
    avaliar_riscos_tarefas,
    calcular_faixa_previsao_termino,
    calcular_indicadores,
    gerar_percepcoes,
    gerar_recomendacoes,
    peso_tarefa,
    simular_alteracao_tarefa,
    simular_conclusao_tarefas,
)

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


def test_recomendacoes_mencionam_tarefa_critica_atrasada(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    recomendacoes = gerar_recomendacoes(projeto_com_custo, ind, idioma="pt")
    assert recomendacoes
    assert all(isinstance(r, str) and r for r in recomendacoes)
    # Este cronograma tem tarefas críticas atrasadas, então a recomendação deve
    # citar pelo menos uma delas nominalmente (não só descrever o problema).
    nomes_criticas_atrasadas = {
        t.nome for t in projeto_com_custo.tarefas_detalhe if t.critica and t.atrasada
    }
    assert any(nome in r for r in recomendacoes for nome in nomes_criticas_atrasadas)


def test_recomendacoes_ingles(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    recomendacoes_en = gerar_recomendacoes(projeto_com_custo, ind, idioma="en")
    assert recomendacoes_en
    assert recomendacoes_en != gerar_recomendacoes(projeto_com_custo, ind, idioma="pt")


def test_recomendacoes_sem_problemas_da_mensagem_neutra():
    from cronograma.metricas import Indicadores

    ind_ok = Indicadores(
        unidade="R$", pv_total=100, ev_total=100, ac_total=100, spi=1.0, cpi=1.0,
        percentual_concluido=100.0, variacao_custo=0, variacao_custo_pct=0,
        variacao_prazo=0, variacao_prazo_pct=0, atraso_dias=0, custo_previsto_total=100,
        tarefas_criticas_atrasadas=0, tarefas_atrasadas=0, total_tarefas=5,
    )

    class ProjetoVazio:
        tarefas_detalhe = []

    recomendacoes = gerar_recomendacoes(ProjetoVazio(), ind_ok, idioma="pt")
    assert len(recomendacoes) == 1
    assert "nenhuma ação urgente" in recomendacoes[0].lower()


def test_faixa_previsao_termino_ordem_cronologica(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    faixa = calcular_faixa_previsao_termino(ind, DATA_STATUS)
    assert faixa.otimista is not None
    assert faixa.realista is not None
    assert faixa.pessimista is not None
    assert faixa.otimista == ind.termino_planejado
    assert faixa.realista == ind.termino_projetado
    # SPI < 1 neste cronograma: o pessimista deve prever ainda mais atraso que o realista.
    assert faixa.pessimista >= faixa.realista


def test_avaliar_riscos_tarefas_ordenado_por_severidade(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    riscos = avaliar_riscos_tarefas(projeto_com_custo)
    assert len(riscos) == ind.tarefas_atrasadas
    severidades = [r["impacto"] * r["probabilidade"] for r in riscos]
    assert severidades == sorted(severidades, reverse=True)
    assert all(1 <= r["impacto"] <= 3 and 1 <= r["probabilidade"] <= 3 for r in riscos)


def test_simular_alteracao_tarefa_nao_afeta_original(projeto_com_custo):
    tarefa_alvo = next(
        t for t in projeto_com_custo.tarefas_detalhe if t.percentual_concluido < 100
    )
    percentual_original = tarefa_alvo.percentual_concluido

    projeto_simulado = simular_alteracao_tarefa(
        projeto_com_custo, tarefa_alvo.uid, novo_percentual=100.0
    )

    assert tarefa_alvo.percentual_concluido == percentual_original
    tarefa_simulada = next(t for t in projeto_simulado.tarefas if t.uid == tarefa_alvo.uid)
    assert tarefa_simulada.percentual_concluido == 100.0

    ind_original = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    ind_simulado = calcular_indicadores(projeto_simulado, DATA_STATUS)
    assert ind_simulado.ev_total > ind_original.ev_total
    assert ind_simulado.percentual_concluido > ind_original.percentual_concluido


def test_simular_conclusao_tarefas_marca_100_por_cento_sem_afetar_original(projeto_com_custo):
    tarefas_nao_concluidas = [t for t in projeto_com_custo.tarefas_detalhe if t.percentual_concluido < 100]
    assert len(tarefas_nao_concluidas) >= 2
    percentuais_originais = [t.percentual_concluido for t in tarefas_nao_concluidas]
    uids = [t.uid for t in tarefas_nao_concluidas]

    projeto_simulado = simular_conclusao_tarefas(projeto_com_custo, uids)

    # Os dados originais não podem ser alterados.
    assert [t.percentual_concluido for t in tarefas_nao_concluidas] == percentuais_originais

    tarefas_simuladas = {t.uid: t for t in projeto_simulado.tarefas}
    assert all(tarefas_simuladas[uid].percentual_concluido == 100.0 for uid in uids)

    ind_original = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    ind_simulado = calcular_indicadores(projeto_simulado, DATA_STATUS)
    assert ind_simulado.percentual_concluido > ind_original.percentual_concluido
    assert ind_simulado.spi > ind_original.spi


def test_simular_conclusao_tarefas_lista_vazia_nao_muda_indicadores(projeto_com_custo):
    projeto_simulado = simular_conclusao_tarefas(projeto_com_custo, [])
    ind_original = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    ind_simulado = calcular_indicadores(projeto_simulado, DATA_STATUS)
    assert ind_simulado.percentual_concluido == pytest.approx(ind_original.percentual_concluido)
