from datetime import date, timedelta

import pandas as pd
import pytest

from cronograma.metricas import (
    avaliar_riscos_tarefas,
    calcular_corrente_critica,
    calcular_faixa_previsao_termino,
    calcular_indicadores,
    detectar_tarefa_buffer,
    gerar_observacoes_simulacao,
    gerar_percepcoes,
    gerar_recomendacoes,
    identificar_sucessoras_diretas,
    peso_tarefa,
    simular_alteracao_tarefa,
    simular_conclusao_tarefas,
    simular_monte_carlo_termino,
)
from cronograma.modelos import Dependencia, Projeto, Tarefa

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


@pytest.fixture()
def projeto_com_dependencias():
    fundacao = Tarefa(uid="1", id=1, nome="Fundação", critica=True)
    estrutura = Tarefa(
        uid="2", id=2, nome="Estrutura", critica=True,
        dependencias=[Dependencia(predecessora_uid="1")],
    )
    acabamento = Tarefa(
        uid="3", id=3, nome="Acabamento", critica=False,
        dependencias=[Dependencia(predecessora_uid="2")],
    )
    isolada = Tarefa(uid="4", id=4, nome="Tarefa isolada", critica=False)
    return Projeto(nome="Projeto com dependências", tarefas=[fundacao, estrutura, acabamento, isolada])


def test_identificar_sucessoras_diretas(projeto_com_dependencias):
    sucessoras_fundacao = identificar_sucessoras_diretas(projeto_com_dependencias, "1")
    assert [t.nome for t in sucessoras_fundacao] == ["Estrutura"]

    sucessoras_isolada = identificar_sucessoras_diretas(projeto_com_dependencias, "4")
    assert sucessoras_isolada == []


def test_gerar_observacoes_simulacao_com_sucessora_critica(projeto_com_dependencias):
    observacoes = gerar_observacoes_simulacao(projeto_com_dependencias, ["1"], idioma="pt")
    assert len(observacoes) == 1
    assert "Estrutura" in observacoes[0]
    assert "caminho crítico" in observacoes[0]


def test_gerar_observacoes_simulacao_sem_sucessoras(projeto_com_dependencias):
    observacoes = gerar_observacoes_simulacao(projeto_com_dependencias, ["4"], idioma="pt")
    assert len(observacoes) == 1
    assert "nenhuma outra tarefa depende diretamente dela" in observacoes[0]
    assert "caminho crítico" not in observacoes[0]


def test_gerar_observacoes_simulacao_ingles(projeto_com_dependencias):
    observacoes_pt = gerar_observacoes_simulacao(projeto_com_dependencias, ["1"], idioma="pt")
    observacoes_en = gerar_observacoes_simulacao(projeto_com_dependencias, ["1"], idioma="en")
    assert observacoes_en != observacoes_pt
    assert "Estrutura" in observacoes_en[0]


@pytest.fixture()
def projeto_cadeia_sequencial():
    """Três tarefas em cadeia (Término-Início): Fundação -> Estrutura -> Acabamento,
    10 dias cada, sem sobreposição — dá pra prever o término exato no caso
    determinístico (sem variabilidade)."""
    hoje = date(2026, 1, 1)
    fundacao = Tarefa(
        uid="1", id=1, nome="Fundação", critica=True, percentual_concluido=0,
        inicio=hoje, termino=hoje + timedelta(days=10),
    )
    estrutura = Tarefa(
        uid="2", id=2, nome="Estrutura", critica=True, percentual_concluido=0,
        inicio=hoje + timedelta(days=10), termino=hoje + timedelta(days=20),
        dependencias=[Dependencia(predecessora_uid="1")],
    )
    acabamento = Tarefa(
        uid="3", id=3, nome="Acabamento", critica=False, percentual_concluido=0,
        inicio=hoje + timedelta(days=20), termino=hoje + timedelta(days=30),
        dependencias=[Dependencia(predecessora_uid="2")],
    )
    projeto = Projeto(nome="Projeto Sequencial", tarefas=[fundacao, estrutura, acabamento])
    return projeto, hoje


def test_monte_carlo_determinístico_bate_com_cpm_manual(projeto_cadeia_sequencial):
    projeto, hoje = projeto_cadeia_sequencial
    resultado = simular_monte_carlo_termino(
        projeto, hoje, n_simulacoes=200, fator_otimista=1.0, fator_pessimista=1.0,
    )
    assert resultado is not None
    # Sem variabilidade, todas as rodadas devem dar exatamente o mesmo término: 30 dias
    # após o início (10 + 10 + 10, em cadeia).
    datas_unicas = set(pd.Timestamp(d).date() for d in resultado.datas_simuladas)
    assert datas_unicas == {hoje + timedelta(days=30)}
    assert resultado.n_tarefas_simuladas == 3


def test_monte_carlo_percentis_ordenados(projeto_cadeia_sequencial):
    projeto, hoje = projeto_cadeia_sequencial
    resultado = simular_monte_carlo_termino(
        projeto, hoje, n_simulacoes=3000, fator_otimista=0.7, fator_pessimista=1.5,
    )
    assert resultado.percentis[10] <= resultado.percentis[50]
    assert resultado.percentis[50] <= resultado.percentis[80]
    assert resultado.percentis[80] <= resultado.percentis[90]
    # Com variabilidade real, nem todas as rodadas devem dar a mesma data.
    assert len(set(pd.Timestamp(d).date() for d in resultado.datas_simuladas)) > 1


def test_monte_carlo_respeita_dependencia_termino_inicio(projeto_cadeia_sequencial):
    """Verificação indireta de que a propagação respeita Término-Início: com uma
    janela de incerteza bem ampla, o término simulado do projeto nunca pode ser menor
    que a duração da primeira tarefa sozinha (senão a cadeia foi ignorada)."""
    projeto, hoje = projeto_cadeia_sequencial
    resultado = simular_monte_carlo_termino(
        projeto, hoje, n_simulacoes=2000, fator_otimista=0.1, fator_pessimista=0.5,
    )
    menor_termino = min(pd.Timestamp(d).date() for d in resultado.datas_simuladas)
    # Mesmo no cenário mais otimista de todos, as 3 tarefas em cadeia não podem
    # terminar antes de ~3 dias (0.1 dia cada, arredondado pelo clip mínimo de 0.1).
    assert menor_termino > hoje


def test_monte_carlo_tarefa_concluida_nao_e_sorteada():
    hoje = date(2026, 1, 1)
    concluida = Tarefa(
        uid="1", id=1, nome="Concluída", percentual_concluido=100,
        inicio=hoje, termino=hoje + timedelta(days=5),
        termino_real=hoje + timedelta(days=5), inicio_real=hoje,
    )
    projeto = Projeto(nome="Projeto com tarefa concluída", tarefas=[concluida])
    resultado = simular_monte_carlo_termino(projeto, hoje, n_simulacoes=100)
    assert resultado is not None
    assert resultado.n_tarefas_simuladas == 0
    datas_unicas = set(pd.Timestamp(d).date() for d in resultado.datas_simuladas)
    assert datas_unicas == {hoje + timedelta(days=5)}


def test_monte_carlo_projeto_sem_tarefas_com_data_retorna_none():
    projeto = Projeto(nome="Vazio", tarefas=[])
    assert simular_monte_carlo_termino(projeto, date(2026, 1, 1)) is None


def _tarefa_critica(uid, nome, pct, inicio, termino, horas=80):
    return Tarefa(
        uid=uid, id=int(uid), nome=nome, critica=True, percentual_concluido=pct,
        inicio=inicio, termino=termino, inicio_linha_base=inicio, termino_linha_base=termino,
        duracao_linha_base_horas=horas,
    )


def test_detectar_tarefa_buffer_encontra_por_nome():
    fase = _tarefa_critica("1", "Fase 1", 100, date(2026, 1, 1), date(2026, 1, 10))
    buffer_tarefa = Tarefa(
        uid="2", id=2, nome="Buffer de Projeto", percentual_concluido=25,
        inicio=date(2026, 1, 10), termino=date(2026, 1, 20), duracao_linha_base_horas=80,
    )
    projeto = Projeto(nome="Com buffer", tarefas=[fase, buffer_tarefa])
    encontrada = detectar_tarefa_buffer(projeto)
    assert encontrada is not None
    assert encontrada.uid == "2"


def test_detectar_tarefa_buffer_sem_correspondencia_retorna_none():
    fase = _tarefa_critica("1", "Fase 1", 100, date(2026, 1, 1), date(2026, 1, 10))
    projeto = Projeto(nome="Sem buffer", tarefas=[fase])
    assert detectar_tarefa_buffer(projeto) is None


def test_calcular_corrente_critica_usa_buffer_detectado():
    fase1 = _tarefa_critica("1", "Fase 1", 100, date(2026, 1, 1), date(2026, 1, 10))
    fase2 = _tarefa_critica("2", "Fase 2", 40, date(2026, 1, 10), date(2026, 1, 25), horas=120)
    buffer_tarefa = Tarefa(
        uid="3", id=3, nome="Buffer de Projeto", percentual_concluido=25,
        inicio=date(2026, 1, 25), termino=date(2026, 2, 4), duracao_linha_base_horas=80,
    )
    projeto = Projeto(nome="Com buffer explícito", tarefas=[fase1, fase2, buffer_tarefa])
    indicadores = calcular_indicadores(projeto, date(2026, 1, 15))

    resultado = calcular_corrente_critica(projeto, indicadores)
    assert resultado is not None
    assert resultado.origem_buffer == "detectado"
    assert resultado.nome_tarefa_buffer == "Buffer de Projeto"
    assert resultado.percentual_buffer_consumido == 25
    assert resultado.buffer_dias == pytest.approx(10.0)
    assert resultado.zona in {"verde", "amarela", "vermelha"}


def test_calcular_corrente_critica_sintetiza_buffer_via_monte_carlo():
    fase1 = _tarefa_critica("1", "Fase 1", 100, date(2026, 1, 1), date(2026, 1, 10))
    fase2 = _tarefa_critica("2", "Fase 2", 40, date(2026, 1, 10), date(2026, 1, 25), horas=120)
    projeto = Projeto(nome="Sem buffer explícito", tarefas=[fase1, fase2])
    data_status = date(2026, 1, 15)
    indicadores = calcular_indicadores(projeto, data_status)
    monte_carlo = simular_monte_carlo_termino(projeto, data_status, n_simulacoes=2000)

    resultado = calcular_corrente_critica(projeto, indicadores, resultado_monte_carlo=monte_carlo)
    assert resultado is not None
    assert resultado.origem_buffer == "sintetico"
    assert resultado.nome_tarefa_buffer is None
    assert resultado.buffer_dias > 0


def test_calcular_corrente_critica_sem_tarefa_critica_nem_monte_carlo_retorna_none():
    tarefa_nao_critica = Tarefa(
        uid="1", id=1, nome="Tarefa qualquer", critica=False, percentual_concluido=50,
        inicio=date(2026, 1, 1), termino=date(2026, 1, 10),
    )
    projeto = Projeto(nome="Sem corrente crítica", tarefas=[tarefa_nao_critica])
    indicadores = calcular_indicadores(projeto, date(2026, 1, 5))
    assert calcular_corrente_critica(projeto, indicadores) is None


def test_calcular_corrente_critica_zona_vermelha_quando_buffer_estourado():
    fase1 = _tarefa_critica("1", "Fase 1", 30, date(2026, 1, 1), date(2026, 1, 10))
    buffer_estourado = Tarefa(
        uid="2", id=2, nome="Pulmão do Projeto", percentual_concluido=95,
        inicio=date(2026, 1, 10), termino=date(2026, 1, 20), duracao_linha_base_horas=80,
    )
    projeto = Projeto(nome="Buffer quase estourado", tarefas=[fase1, buffer_estourado])
    indicadores = calcular_indicadores(projeto, date(2026, 1, 5))
    resultado = calcular_corrente_critica(projeto, indicadores)
    assert resultado.zona == "vermelha"


def test_calcular_corrente_critica_reconstrói_via_cadeia_do_buffer_sem_tarefa_critica():
    # Simula uma ferramenta de CCPM dedicada (ex.: Concerto) que não marca
    # tarefa.critica no MS Project — só insere o buffer de projeto no fim da cadeia.
    marco_entrada = Tarefa(
        uid="1", id=1, nome="Marco de entrada", marco=True, critica=False,
        percentual_concluido=100, inicio=date(2026, 1, 1), termino=date(2026, 1, 1),
    )
    fase1 = Tarefa(
        uid="2", id=2, nome="Fase 1", critica=False, percentual_concluido=100,
        inicio=date(2026, 1, 1), termino=date(2026, 1, 10), duracao_linha_base_horas=80,
        dependencias=[Dependencia(predecessora_uid="1")],
    )
    fase2 = Tarefa(
        uid="3", id=3, nome="Fase 2", critica=False, percentual_concluido=40,
        inicio=date(2026, 1, 10), termino=date(2026, 1, 25), duracao_linha_base_horas=120,
        dependencias=[Dependencia(predecessora_uid="2")],
    )
    # Feeding buffer de uma perna secundária que também alimenta a Fase 2 — não deve
    # ser incluído na corrente crítica reconstruída, nem suas próprias predecessoras.
    tarefa_secundaria = Tarefa(
        uid="9", id=9, nome="Tarefa de outra perna", critica=False, percentual_concluido=0,
        inicio=date(2026, 1, 1), termino=date(2026, 1, 5),
    )
    feeding_buffer = Tarefa(
        uid="10", id=10, nome="Feeding Buffer", critica=False, percentual_concluido=0,
        inicio=date(2026, 1, 5), termino=date(2026, 1, 9),
        dependencias=[Dependencia(predecessora_uid="9")],
    )
    fase2.dependencias.append(Dependencia(predecessora_uid="10"))
    buffer_projeto = Tarefa(
        uid="4", id=4, nome="Project Buffer", critica=False, percentual_concluido=25,
        inicio=date(2026, 1, 25), termino=date(2026, 2, 4), duracao_linha_base_horas=80,
        dependencias=[Dependencia(predecessora_uid="3")],
    )
    projeto = Projeto(
        nome="CCPM sem campo crítico",
        tarefas=[marco_entrada, fase1, fase2, tarefa_secundaria, feeding_buffer, buffer_projeto],
    )
    indicadores = calcular_indicadores(projeto, date(2026, 1, 15))

    resultado = calcular_corrente_critica(projeto, indicadores)
    assert resultado is not None
    assert resultado.origem_corrente == "cadeia_via_buffer"
    assert resultado.origem_buffer == "detectado"
    assert resultado.nome_tarefa_buffer == "Project Buffer"
    # A tarefa da perna secundária (e o feeding buffer que a sucede) não fazem parte
    # da corrente crítica reconstruída, só do caminho principal via marco/fase1/fase2.
    assert 0 < resultado.percentual_corrente_critica_concluida < 100


def test_calcular_corrente_critica_usa_campo_critico_quando_disponivel():
    # Quando tarefa.critica já está preenchido (MS Project tradicional), a origem
    # continua sendo "critica_ms_project", sem acionar a reconstrução via buffer.
    fase1 = _tarefa_critica("1", "Fase 1", 100, date(2026, 1, 1), date(2026, 1, 10))
    fase2 = _tarefa_critica("2", "Fase 2", 40, date(2026, 1, 10), date(2026, 1, 25), horas=120)
    buffer_tarefa = Tarefa(
        uid="3", id=3, nome="Buffer de Projeto", percentual_concluido=25,
        inicio=date(2026, 1, 25), termino=date(2026, 2, 4), duracao_linha_base_horas=80,
    )
    projeto = Projeto(nome="Com campo crítico", tarefas=[fase1, fase2, buffer_tarefa])
    indicadores = calcular_indicadores(projeto, date(2026, 1, 15))
    resultado = calcular_corrente_critica(projeto, indicadores)
    assert resultado.origem_corrente == "critica_ms_project"
