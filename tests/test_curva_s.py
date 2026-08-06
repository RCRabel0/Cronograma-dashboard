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
    assert {"WBS", "Tarefa", "Crítica", "Atrasada", "Percentual Concluído", "Linha", "Peso (%)"} <= set(df.columns)
    assert set(df["Linha"].unique()) == {"Planejado", "Realizado"}
    # Duas linhas (Planejado + Realizado) por tarefa de detalhe.
    assert len(df) == 2 * len(projeto_com_custo.tarefas_detalhe)
    # 'exemplo_cronograma.xml' é um cronograma plano (todas as tarefas no nível 1), então
    # o WBS de cada uma é um único número sequencial, sem pontos.
    assert all("." not in wbs for wbs in df["WBS"])


def test_ff_celula_sem_alocacao_fica_nan_nao_none(projeto_com_custo):
    # Bug corrigido: quando NENHUMA tarefa tem alocação num mês, a coluna inteira ficava
    # com dtype 'object' cheio de None (em vez de float64 com NaN), e o Streamlit exibia
    # o texto literal "None" na célula em vez de deixá-la em branco.
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    colunas_mes = [
        c for c in df.columns
        if c not in ("WBS", "Tarefa", "Crítica", "Atrasada", "Percentual Concluído", "Linha", "Peso (%)")
    ]
    for coluna in colunas_mes:
        assert df[coluna].dtype.kind == "f", f"coluna {coluna} não é float64: {df[coluna].dtype}"


def test_ff_nivel_maximo_wbs_configuravel(projeto_com_custo):
    df_nivel_1 = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS, nivel_maximo_wbs=1)
    # 'exemplo_cronograma.xml' é plano (nível 1), então mesmo limitando a 1 nível o WBS
    # continua um único número sequencial — o teste de achatamento real está em
    # test_ff_wbs_numera_hierarquia_ate_4_niveis, que usa uma hierarquia sintética.
    assert all("." not in wbs for wbs in df_nivel_1["WBS"])


def test_ff_peso_soma_100(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    peso_por_tarefa = df[df["Linha"] == "Planejado"]["Peso (%)"]
    assert peso_por_tarefa.sum() == pytest.approx(100.0, rel=1e-6)


def test_ff_planejado_soma_bate_peso_da_tarefa(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    colunas_mes = [
        c for c in df.columns
        if c not in ("WBS", "Tarefa", "Crítica", "Atrasada", "Percentual Concluído", "Linha", "Peso (%)")
    ]
    planejado = df[df["Linha"] == "Planejado"]
    for _, linha in planejado.iterrows():
        soma_meses = sum(v for v in (linha[c] for c in colunas_mes) if v is not None and v == v)
        assert soma_meses == pytest.approx(linha["Peso (%)"], abs=0.05)


def test_ff_realizado_reflete_percentual_concluido(projeto_com_custo):
    df = gerar_tabela_fisico_financeiro(projeto_com_custo, DATA_STATUS)
    colunas_mes = [
        c for c in df.columns
        if c not in ("WBS", "Tarefa", "Crítica", "Atrasada", "Percentual Concluído", "Linha", "Peso (%)")
    ]
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


def _projeto_hierarquico():
    from cronograma.modelos import Projeto, Tarefa

    def _t(uid, nome, nivel, resumo=False, **kwargs):
        return Tarefa(uid=uid, id=int(uid), nome=nome, nivel_esquema=nivel, resumo=resumo, **kwargs)

    tarefas = [
        _t("1", "Fase 1", 1, resumo=True),
        _t("2", "Sub 1.1", 2, resumo=True),
        _t(
            "3", "Ativ 1.1.1", 3,
            inicio=date(2026, 1, 1), termino=date(2026, 1, 10),
            inicio_linha_base=date(2026, 1, 1), termino_linha_base=date(2026, 1, 10),
            inicio_real=date(2026, 1, 1), termino_real=date(2026, 1, 10),
            duracao_linha_base_horas=60, percentual_concluido=100,
        ),
        _t(
            "4", "Ativ 1.1.2", 3,
            inicio=date(2026, 1, 10), termino=date(2026, 1, 20),
            inicio_linha_base=date(2026, 1, 10), termino_linha_base=date(2026, 1, 20),
            inicio_real=date(2026, 1, 10), termino_real=date(2026, 1, 15),
            duracao_linha_base_horas=40, percentual_concluido=50,
        ),
        _t(
            "5", "Sub 1.2", 2,
            inicio=date(2026, 1, 20), termino=date(2026, 1, 31),
            inicio_linha_base=date(2026, 1, 20), termino_linha_base=date(2026, 1, 31),
            duracao_linha_base_horas=100, percentual_concluido=0,
        ),
    ]
    return Projeto(nome="Hierárquico", tarefas=tarefas)


def test_ff_wbs_numera_hierarquia_completa_sem_achatamento():
    df = gerar_tabela_fisico_financeiro(_projeto_hierarquico(), date(2026, 1, 31), nivel_maximo_wbs=3)
    wbs_por_tarefa = dict(zip(df["Tarefa"], df["WBS"]))
    assert wbs_por_tarefa["Fase 1"] == "1"
    assert wbs_por_tarefa["Sub 1.1"] == "1.1"
    assert wbs_por_tarefa["Ativ 1.1.1"] == "1.1.1"
    assert wbs_por_tarefa["Ativ 1.1.2"] == "1.1.2"
    assert wbs_por_tarefa["Sub 1.2"] == "1.2"


def test_ff_nivel_1_mostra_so_a_raiz_com_peso_total():
    df = gerar_tabela_fisico_financeiro(_projeto_hierarquico(), date(2026, 1, 31), nivel_maximo_wbs=1)
    assert set(df["WBS"]) == {"1"}
    assert df[df["Linha"] == "Planejado"]["Peso (%)"].iloc[0] == pytest.approx(100.0)


def test_ff_nivel_2_acumula_niveis_1_e_2():
    # Pedido do usuário: selecionar o nível 2 tem que mostrar os níveis 1 E 2 juntos
    # (acumulado), não só o nível 2 isolado.
    df = gerar_tabela_fisico_financeiro(_projeto_hierarquico(), date(2026, 1, 31), nivel_maximo_wbs=2)
    assert set(df["WBS"]) == {"1", "1.1", "1.2"}

    peso_por_wbs = df[df["Linha"] == "Planejado"].set_index("WBS")["Peso (%)"]
    # Sub 1.1 (peso 30+20=50) e Sub 1.2 (peso 100) somam os pesos de "Ativ 1.1.1" (30%),
    # "Ativ 1.1.2" (20%) e "Sub 1.2" (50%) sobre o total de 200 (60+40+100).
    assert peso_por_wbs["1.1"] == pytest.approx(50.0)
    assert peso_por_wbs["1.2"] == pytest.approx(50.0)
    assert peso_por_wbs["1"] == pytest.approx(100.0)


def test_ff_nivel_3_mostra_tudo_e_resumo_agrega_filhos():
    df = gerar_tabela_fisico_financeiro(_projeto_hierarquico(), date(2026, 1, 31), nivel_maximo_wbs=3)
    assert set(df["WBS"]) == {"1", "1.1", "1.1.1", "1.1.2", "1.2"}

    # % Concluído agregado: Ativ 1.1.1 (peso 30, 100% concluída) + Ativ 1.1.2 (peso 20,
    # 50% concluída = 10 realizado) + Sub 1.2 (peso 50, 0% concluída) = 40 realizado
    # sobre 100 de peso total da Fase 1 -> 40%.
    linha_fase1 = df[(df["WBS"] == "1") & (df["Linha"] == "Planejado")].iloc[0]
    assert linha_fase1["Percentual Concluído"] == pytest.approx(40.0, abs=0.1)

    linha_sub11 = df[(df["WBS"] == "1.1") & (df["Linha"] == "Planejado")].iloc[0]
    # Sub 1.1 agrega só Ativ 1.1.1 (30, 100%) e Ativ 1.1.2 (20, 50%=10) -> 40/50 = 80%.
    assert linha_sub11["Percentual Concluído"] == pytest.approx(80.0, abs=0.1)
