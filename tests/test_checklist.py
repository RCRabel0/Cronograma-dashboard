import copy
from datetime import date

from cronograma.checklist import avaliar_checklist, calcular_pontuacao
from cronograma.metricas import calcular_indicadores

DATA_STATUS = date(2026, 7, 24)


def _item(itens, trecho):
    return next(i for i in itens if trecho in i.texto)


def test_checklist_avalia_itens(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    itens = avaliar_checklist(projeto_com_custo, ind, idioma="pt")
    assert itens
    assert all(item.status in ("Conforme", "Parcial", "Não Conforme", "N/A") for item in itens)
    assert all(item.secao and item.texto for item in itens)


def test_pontuacao_consistente(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    itens = avaliar_checklist(projeto_com_custo, ind, idioma="pt")
    pontuacao = calcular_pontuacao(itens)
    assert 0 <= pontuacao["percentual"] <= 100
    assert pontuacao["pontos"] <= pontuacao["maximo"]
    assert pontuacao["itens_avaliados"] <= pontuacao["total_itens"]
    assert pontuacao["classificacao"]


def test_checklist_sem_custo_nao_quebra(projeto_sem_custo):
    ind = calcular_indicadores(projeto_sem_custo, DATA_STATUS)
    itens = avaliar_checklist(projeto_sem_custo, ind, idioma="pt")
    assert itens


def test_progresso_sem_inicio_real_conforme(projeto_com_custo):
    ind = calcular_indicadores(projeto_com_custo, DATA_STATUS)
    itens = avaliar_checklist(projeto_com_custo, ind, idioma="pt")
    item = _item(itens, "possuem data real de início")
    assert item.status == "Conforme"


def test_progresso_sem_inicio_real_detecta_inconsistencia(projeto_com_custo):
    projeto = copy.deepcopy(projeto_com_custo)
    tarefa_com_progresso = next(t for t in projeto.tarefas_detalhe if t.percentual_concluido > 0)
    tarefa_com_progresso.inicio_real = None

    ind = calcular_indicadores(projeto, DATA_STATUS)
    itens = avaliar_checklist(projeto, ind, idioma="pt")
    item = _item(itens, "possuem data real de início")
    assert item.status in ("Parcial", "Não Conforme")
    assert tarefa_com_progresso.nome in item.evidencia
