import os
import tempfile
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from cronograma.checklist import avaliar_checklist, calcular_pontuacao
from cronograma.curva_s import gerar_curva_s
from cronograma.i18n import formatar_data, formato_coluna_data, t, tf
from cronograma.leitor_mpp import MpxjIndisponivelError, ler_mpp
from cronograma.leitor_xml import ArquivoInvalidoError, ler_xml
from cronograma.metricas import (
    calcular_indicadores,
    dias_atraso_tarefa,
    formatar_valor,
    gerar_percepcoes,
)
from cronograma.portfolio import (
    calcular_indicadores_portfolio,
    gerar_curva_s_portfolio,
    indicadores_consolidados,
    pesos_relativos,
    tabela_comparativa,
)
from cronograma.relatorios import (
    gerar_excel,
    gerar_excel_portfolio,
    gerar_excel_tabela,
    gerar_pdf,
    gerar_pdf_executivo,
    gerar_pdf_portfolio,
    tabela_recursos,
    tabela_tarefas,
)

_idioma_salvo = st.session_state.get("idioma_ui", "Português")
_idioma_inicial = "en" if _idioma_salvo == "English" else "pt"

st.set_page_config(
    page_title=t("Dashboard de Cronograma de Projeto", _idioma_inicial),
    page_icon="📊",
    layout="wide",
)

idioma_escolha = st.sidebar.segmented_control(
    "Idioma / Language", ["Português", "English"], default="Português", key="idioma_ui", required=True
)
idioma = "en" if idioma_escolha == "English" else "pt"
st.sidebar.divider()


@st.cache_data(show_spinner=t("Lendo e interpretando o cronograma...", idioma))
def processar_arquivo(conteudo: bytes, nome_arquivo: str):
    sufixo = os.path.splitext(nome_arquivo)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
        tmp.write(conteudo)
        caminho = tmp.name
    try:
        if sufixo == ".xml":
            return ler_xml(caminho)
        elif sufixo == ".mpp":
            return ler_mpp(caminho)
        else:
            raise ValueError("Formato de arquivo não suportado. Envie um arquivo .xml ou .mpp.")
    finally:
        os.unlink(caminho)


st.sidebar.title(t("📁 Cronograma", idioma))
arquivos = st.sidebar.file_uploader(
    t("Envie o(s) arquivo(s) do cronograma", idioma),
    type=["xml", "mpp"],
    accept_multiple_files=True,
    help=t(
        "Arquivo .mpp do MS Project, ou .xml exportado via Arquivo > Salvar Como > XML. "
        "Envie mais de um arquivo para ver a aba de Portfólio.",
        idioma,
    ),
)

if arquivos:
    projetos_carregados = {}
    for arquivo in arquivos:
        try:
            projetos_carregados[arquivo.name] = processar_arquivo(arquivo.getvalue(), arquivo.name)
        except ArquivoInvalidoError as e:
            st.sidebar.error(tf("Não foi possível ler o arquivo {nome}: {erro}", idioma, nome=arquivo.name, erro=e))
        except MpxjIndisponivelError as e:
            st.sidebar.error(str(e))
        except ValueError as e:
            st.sidebar.error(str(e))
        except Exception as e:
            st.sidebar.error(tf("Ocorreu um erro inesperado ao ler o arquivo {nome}: {erro}", idioma, nome=arquivo.name, erro=e))
    if projetos_carregados:
        st.session_state["projetos"] = projetos_carregados

if not st.session_state.get("projetos"):
    st.title(t("📊 Dashboard de Cronograma de Projeto", idioma))
    st.info(
        t(
            "👈 Envie um arquivo **.xml** (exportado do MS Project) ou **.mpp** na barra lateral para começar.\n\n"
            "Para exportar o XML no MS Project: **Arquivo > Salvar Como**, escolha o tipo **XML**.",
            idioma,
        )
    )
    st.stop()

projetos = st.session_state["projetos"]
portfolio_ativo = len(projetos) > 1
if portfolio_ativo:
    nome_projeto_atual = st.sidebar.selectbox(t("Projeto para detalhamento", idioma), list(projetos.keys()))
else:
    nome_projeto_atual = next(iter(projetos))
projeto = projetos[nome_projeto_atual]

data_padrao = projeto.data_status or date.today()
data_status = st.sidebar.date_input(t("Data de status (para cálculo dos indicadores)", idioma), value=data_padrao)
if isinstance(data_status, tuple):
    data_status = data_status[0]

indicadores = calcular_indicadores(projeto, data_status)
percepcoes = gerar_percepcoes(projeto, indicadores, idioma=idioma)
# Os relatórios exportados (Excel/PDF) permanecem sempre em português, independente do idioma da interface.
percepcoes_exportacao = [texto for _categoria, texto in gerar_percepcoes(projeto, indicadores, idioma="pt")]
curva = gerar_curva_s(projeto, data_status, percentual_concluido_alvo=indicadores.percentual_concluido)

# Período global compartilhado entre as abas: ajustar o período em qualquer aba atualiza
# automaticamente os filtros de período das demais.
_todas_datas_projeto = []
for _t in projeto.tarefas_detalhe:
    _todas_datas_projeto += [_t.inicio, _t.termino, _t.inicio_linha_base, _t.termino_linha_base]
_todas_datas_projeto = [d for d in _todas_datas_projeto if d is not None]
data_min_projeto = min(_todas_datas_projeto) if _todas_datas_projeto else date.today()
data_max_projeto = max(_todas_datas_projeto) if _todas_datas_projeto else date.today()

if "periodo_global" not in st.session_state:
    st.session_state["periodo_global"] = (data_min_projeto, data_max_projeto)
if "periodo_versao" not in st.session_state:
    st.session_state["periodo_versao"] = 0


def obter_periodo_global() -> tuple[date, date]:
    inicio, fim = st.session_state["periodo_global"]
    inicio = max(inicio, data_min_projeto)
    fim = min(fim, data_max_projeto)
    if inicio > fim:
        inicio, fim = data_min_projeto, data_max_projeto
    return inicio, fim


def definir_periodo_global(inicio: date, fim: date) -> None:
    """Atualiza o período global e muda de 'versão', forçando os widgets de período das
    outras abas a se recriarem com o novo valor (em vez de mexer diretamente no estado
    interno deles, o que quebra a serialização de alguns widgets de intervalo)."""
    if st.session_state["periodo_global"] != (inicio, fim):
        st.session_state["periodo_global"] = (inicio, fim)
        st.session_state["periodo_versao"] += 1


if st.sidebar.button(t("🧹 Limpar filtro de datas", idioma)):
    definir_periodo_global(data_min_projeto, data_max_projeto)

if portfolio_ativo:
    st.title(t("📊 Portfólio", idioma))
    st.caption(tf("**Detalhando o projeto:** {v}", idioma, v=projeto.nome))
else:
    st.title(f"📊 {projeto.nome}")
info_cols = st.columns(3)
info_cols[0].caption(tf("**Início:** {v}", idioma, v=formatar_data(projeto.inicio, idioma) if projeto.inicio else t("N/D", idioma)))
info_cols[1].caption(tf("**Término:** {v}", idioma, v=formatar_data(projeto.termino, idioma) if projeto.termino else t("N/D", idioma)))
info_cols[2].caption(tf("**Data de status:** {v}", idioma, v=formatar_data(data_status, idioma)))

_nomes_abas = []
if portfolio_ativo:
    _nomes_abas.append(t("📊 Portfólio", idioma))
_nomes_abas += [
    t("📈 Resumo", idioma),
    t("📉 Curva S", idioma),
    t("✅ Tarefas", idioma),
    t("📅 Gantt", idioma),
    t("📋 Checklist de Qualidade", idioma),
    t("👥 Recursos", idioma),
    t("📤 Exportar", idioma),
]
_abas = st.tabs(_nomes_abas)
if portfolio_ativo:
    aba_portfolio, aba_resumo, aba_curva, aba_tarefas, aba_gantt, aba_checklist, aba_recursos, aba_exportar = _abas
else:
    aba_resumo, aba_curva, aba_tarefas, aba_gantt, aba_checklist, aba_recursos, aba_exportar = _abas

if portfolio_ativo:
    with aba_portfolio:
        st.subheader(t("Portfólio de Projetos", idioma))

        indicadores_portfolio = calcular_indicadores_portfolio(projetos)
        consolidado = indicadores_consolidados(projetos, indicadores_portfolio)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("Projetos", idioma), consolidado["total_projetos"])
        c2.metric(t("% Concluído", idioma), f"{consolidado['percentual_concluido']:.1f}%")
        c3.metric("SPI", f"{consolidado['spi']:.2f}" if consolidado["spi"] is not None else t("N/D", idioma))
        c4.metric("CPI", f"{consolidado['cpi']:.2f}" if consolidado["cpi"] is not None else t("N/D", idioma))

        c5, c6, c7, c8 = st.columns(4)
        c5.metric(t("Projetos Atrasados", idioma), consolidado["projetos_atrasados"])
        c6.metric(t("Tarefas Atrasadas", idioma), consolidado["tarefas_atrasadas"])
        c7.metric(t("Críticas Atrasadas", idioma), consolidado["tarefas_criticas_atrasadas"])
        c8.metric(t("Total de Tarefas", idioma), consolidado["total_tarefas"])

        st.divider()
        st.subheader(t("Comparativo entre Projetos", idioma))
        tabela_port = tabela_comparativa(projetos, indicadores_portfolio, idioma=idioma)
        st.dataframe(tabela_port, hide_index=True, width="stretch")

        st.divider()
        st.subheader(t("Curva S Consolidada do Portfólio", idioma))
        curva_portfolio = gerar_curva_s_portfolio(projetos, indicadores_portfolio)
        if curva_portfolio.empty:
            st.info(t("Não foi possível gerar a Curva S consolidada (sem dados de valor nos projetos).", idioma))
        else:
            ocultar_nomes_termino = st.checkbox(t("Ocultar nomes dos projetos no indicador de término", idioma))
            fig_port = go.Figure()
            fig_port.add_trace(
                go.Scatter(
                    x=curva_portfolio.index, y=curva_portfolio["Linha de Base"],
                    name=t("Linha de Base", idioma), line=dict(dash="dash", color="#5B8DB8"),
                    hovertemplate="%{y:.1f}%",
                )
            )
            fig_port.add_trace(
                go.Scatter(
                    x=curva_portfolio.index, y=curva_portfolio["Realizado / Previsto"],
                    name=t("Realizado / Previsto", idioma), line=dict(color="#2E8B57"),
                    hovertemplate="%{y:.1f}%",
                )
            )
            for _i_proj, (_nome_proj, _p_proj) in enumerate(projetos.items()):
                if _p_proj.termino is None:
                    continue
                fig_port.add_vline(
                    x=pd.Timestamp(_p_proj.termino),
                    line_dash="dot",
                    line_color="#999999",
                    annotation_text="" if ocultar_nomes_termino else _p_proj.nome,
                    annotation_position="top" if _i_proj % 2 == 0 else "bottom",
                    annotation_textangle=-90,
                    annotation_font_size=9,
                )
            fig_port.update_layout(
                xaxis_title=t("Data", idioma),
                yaxis_title=t("% Concluído (acumulado)", idioma),
                hovermode="x unified",
                legend_title_text=t("Série", idioma),
                height=480,
            )
            fig_port.update_yaxes(ticksuffix="%")
            st.plotly_chart(fig_port, width="stretch")
            st.caption(t("As linhas pontilhadas verticais marcam o término (atual) de cada projeto.", idioma))

            with st.expander(t("ℹ️ Como a Curva S do Portfólio foi calculada", idioma)):
                st.write(
                    t(
                        "Cada projeto é normalizado para % do seu próprio valor total (custo, "
                        "ou duração quando não há custo) antes de ser combinado — isso permite somar "
                        "cronogramas com unidades diferentes. A curva final é a média dessas curvas em "
                        "%, ponderada pelo peso de cada projeto (duração total das tarefas), listado abaixo:",
                        idioma,
                    )
                )
                pesos = pesos_relativos(projetos)
                df_pesos = pd.DataFrame(
                    [
                        {
                            t("Projeto", idioma): projetos[nome].nome,
                            t("Peso no Portfólio", idioma): f"{peso:.1f}%",
                        }
                        for nome, peso in pesos.items()
                    ]
                )
                st.dataframe(df_pesos, hide_index=True, width="stretch")

        st.divider()
        st.subheader(t("Exportar Relatório do Portfólio", idioma))
        # O relatório exportado permanece sempre em português, independente do idioma da interface.
        tabela_port_exportacao = tabela_comparativa(projetos, indicadores_portfolio, idioma="pt")
        col_xp, col_pp = st.columns(2)
        with col_xp:
            excel_portfolio_bytes = gerar_excel_portfolio(tabela_port_exportacao, consolidado, curva_portfolio)
            st.download_button(
                t("⬇️ Baixar Excel", idioma),
                data=excel_portfolio_bytes,
                file_name=f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        with col_pp:
            pdf_portfolio_bytes = gerar_pdf_portfolio(tabela_port_exportacao, consolidado, curva_portfolio)
            st.download_button(
                t("⬇️ Baixar PDF", idioma),
                data=pdf_portfolio_bytes,
                file_name=f"portfolio_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                width="stretch",
            )

with aba_resumo:
    c1, c2 = st.columns(2)
    c1.metric(t("% Concluído", idioma), f"{indicadores.percentual_concluido:.1f}%")
    c2.metric(t("Atraso", idioma), tf("{n} dia(s)", idioma, n=indicadores.atraso_dias))

    st.subheader(t("Principais Percepções", idioma))
    for categoria, texto in percepcoes:
        if categoria == "alerta":
            st.warning(texto)
        elif categoria == "info":
            st.info(texto)
        else:
            st.success(texto)

    st.subheader(tf("Tarefas Atrasadas ({n})", idioma, n=indicadores.tarefas_atrasadas))
    tarefas_atrasadas_lista = [tarefa for tarefa in projeto.tarefas_detalhe if tarefa.atrasada]
    if tarefas_atrasadas_lista:
        col_atraso = t("Atraso (dias)", idioma)
        col_inicio = t("Início", idioma)
        col_termino = t("Término", idioma)
        col_termino_lb = t("Término (linha de base)", idioma)
        atrasadas_df = pd.DataFrame(
            [
                {
                    t("Tarefa", idioma): tarefa.nome,
                    t("Crítica", idioma): t("Sim", idioma) if tarefa.critica else t("Não", idioma),
                    col_inicio: tarefa.inicio,
                    col_termino: tarefa.termino,
                    col_termino_lb: tarefa.termino_linha_base,
                    col_atraso: dias_atraso_tarefa(tarefa),
                    t("% Concluído", idioma): tarefa.percentual_concluido,
                }
                for tarefa in tarefas_atrasadas_lista
            ]
        ).sort_values(col_atraso, ascending=False)
        st.dataframe(
            atrasadas_df,
            hide_index=True,
            width="stretch",
            column_config={
                col_inicio: st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                col_termino: st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                col_termino_lb: st.column_config.DateColumn(format=formato_coluna_data(idioma)),
            },
        )
    else:
        st.success(t("Nenhuma tarefa está atrasada em relação à linha de base.", idioma))

    rotulo_ac = t("Custo Real (AC)", idioma) if indicadores.unidade == "R$" else t("Trabalho Real (AC)", idioma)
    rotulo_eac = t("Custo Previsto ao Término (EAC)", idioma) if indicadores.unidade == "R$" else t("Trabalho Previsto ao Término (EAC)", idioma)
    st.subheader(t("Resumo Financeiro", idioma) if indicadores.unidade == "R$" else t("Resumo de Trabalho", idioma))
    resumo_df = pd.DataFrame(
        {
            t("Métrica", idioma): [t("Valor Planejado (PV)", idioma), t("Valor Agregado (EV)", idioma), rotulo_ac, rotulo_eac],
            t("Valor", idioma): [
                formatar_valor(indicadores.pv_total, indicadores.unidade),
                formatar_valor(indicadores.ev_total, indicadores.unidade),
                formatar_valor(indicadores.ac_total, indicadores.unidade),
                formatar_valor(indicadores.custo_previsto_total, indicadores.unidade) if indicadores.custo_previsto_total else t("N/D", idioma),
            ],
        }
    )
    st.dataframe(resumo_df, hide_index=True, width="stretch")

with aba_curva:
    st.subheader(t("Curva S — Linha de Base x Realizado/Previsto", idioma))

    if not projeto.tem_custo:
        ocultar_aviso_unidade = st.checkbox(t("Ocultar aviso sobre unidade de medida", idioma), key="ocultar_aviso_unidade")
        if not ocultar_aviso_unidade:
            st.info(
                t(
                    "ℹ️ Este arquivo não tem custos de recursos preenchidos no MS Project. "
                    "Os indicadores e a Curva S abaixo foram calculados usando **horas de duração** "
                    "(planejada x realizada) como proxy de valor, em vez de custo em R$.",
                    idioma,
                )
            )

    data_min_curva = curva.index.min().date()
    data_max_curva = curva.index.max().date()
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])
    with col_ctrl1:
        if data_min_curva == data_max_curva:
            filtro_inicio_curva, filtro_fim_curva = data_min_curva, data_max_curva
            st.caption(tf("Dados disponíveis apenas para {data}.", idioma, data=formatar_data(data_min_curva, idioma)))
        else:
            _versao = st.session_state["periodo_versao"]
            _g_inicio, _g_fim = obter_periodo_global()
            _curva_inicio = max(_g_inicio, data_min_curva)
            _curva_fim = min(_g_fim, data_max_curva)
            if _curva_inicio > _curva_fim:
                _curva_inicio, _curva_fim = data_min_curva, data_max_curva
            _chave_curva = f"curva_periodo_v{_versao}"

            def _on_change_curva_periodo(_chave=_chave_curva):
                valor = st.session_state[_chave]
                if isinstance(valor, (tuple, list)) and len(valor) == 2:
                    definir_periodo_global(valor[0], valor[1])

            periodo_curva = st.date_input(
                t("Filtrar por data", idioma),
                value=(_curva_inicio, _curva_fim),
                min_value=data_min_curva,
                max_value=data_max_curva,
                key=_chave_curva,
                on_change=_on_change_curva_periodo,
                format=formato_coluna_data(idioma),
            )
            if isinstance(periodo_curva, (tuple, list)) and len(periodo_curva) == 2:
                filtro_inicio_curva, filtro_fim_curva = periodo_curva
            else:
                filtro_inicio_curva, filtro_fim_curva = data_min_curva, data_max_curva
    with col_ctrl2:
        mostrar_percentual = st.toggle(t("Exibir em %", idioma), value=True)
    with col_ctrl3:
        _rotulo_ano = t("Ano", idioma)
        _rotulo_mes = t("Mês", idioma)
        granularidade = st.segmented_control(t("Eixo horizontal", idioma), [_rotulo_ano, _rotulo_mes], default=_rotulo_ano, required=True)

    curva_filtrada = curva.loc[pd.Timestamp(filtro_inicio_curva) : pd.Timestamp(filtro_fim_curva)]

    total_projeto = curva["Linha de Base"].max()

    _nome_linha_base = t("Linha de Base", idioma)
    _nome_realizado = t("Realizado / Previsto", idioma)
    if mostrar_percentual:
        y_linha_base = (curva_filtrada["Linha de Base"] / total_projeto * 100) if total_projeto > 0 else curva_filtrada["Linha de Base"]
        y_executado = (curva_filtrada["Realizado / Previsto"] / total_projeto * 100) if total_projeto > 0 else curva_filtrada["Realizado / Previsto"]
        eixo_y = t("% Concluído (acumulado)", idioma)
        formato_hover = "%{y:.1f}%"
    else:
        y_linha_base = curva_filtrada["Linha de Base"]
        y_executado = curva_filtrada["Realizado / Previsto"]
        eixo_y = t("Custo acumulado (R$)", idioma) if indicadores.unidade == "R$" else t("Trabalho acumulado (horas)", idioma)
        formato_hover = "%{y:,.2f}"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curva_filtrada.index, y=y_linha_base, name=_nome_linha_base, line=dict(dash="dash", color="#5B8DB8"), hovertemplate=formato_hover))
    fig.add_trace(go.Scatter(x=curva_filtrada.index, y=y_executado, name=_nome_realizado, line=dict(color="#2E8B57"), hovertemplate=formato_hover))
    fig.add_vline(x=pd.Timestamp(data_status), line_dash="dot", line_color="gray", annotation_text=t("Data de status", idioma))
    fig.update_layout(
        xaxis_title=t("Data", idioma),
        yaxis_title=eixo_y,
        hovermode="x unified",
        legend_title_text=t("Série", idioma),
        height=520,
    )
    if granularidade == _rotulo_mes:
        fig.update_xaxes(dtick="M1", tickformat="%b/%Y")
    else:
        fig.update_xaxes(dtick="M12", tickformat="%Y")
    if mostrar_percentual:
        fig.update_yaxes(ticksuffix="%")
    st.plotly_chart(fig, width="stretch")
    unidade_texto = t("custo", idioma) if indicadores.unidade == "R$" else t("duração (em horas)", idioma)
    st.caption(
        tf(
            "'Linha de Base' distribui o {unidade} planejado de cada tarefa entre o Início e Término da linha de base. "
            "'Realizado / Previsto' mostra o progresso real (% concluído de cada tarefa) até a data de status e, "
            "a partir dali, segue o ritmo do cronograma atual (já com atrasos/replanejamentos) até o fim do projeto. "
            "O ponto na data de status bate exatamente com o card \"% Concluído\" do Resumo.",
            idioma,
            unidade=unidade_texto,
        )
    )

with aba_tarefas:
    st.subheader(t("Tarefas", idioma))
    col_f1, col_f2 = st.columns(2)
    somente_atrasadas = col_f1.checkbox(t("Mostrar apenas tarefas atrasadas", idioma))
    somente_criticas = col_f2.checkbox(t("Mostrar apenas tarefas críticas", idioma))

    tabela = tabela_tarefas(projeto)
    if somente_atrasadas:
        tabela = tabela[tabela["Atrasada"] == "Sim"]
    if somente_criticas:
        tabela = tabela[tabela["Crítica"] == "Sim"]

    def _destacar_linha(linha):
        if linha["Atrasada"] == "Sim" and linha["Crítica"] == "Sim":
            cor = "background-color: #f1948a"
        elif linha["Atrasada"] == "Sim":
            cor = "background-color: #f8d7da"
        elif linha["Crítica"] == "Sim":
            cor = "background-color: #d7bde2"
        else:
            cor = ""
        return [cor] * len(linha)

    st.dataframe(
        tabela.style.apply(_destacar_linha, axis=1),
        hide_index=True,
        width="stretch",
        column_config={
            "Início": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
            "Término": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
            "Início (linha de base)": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
            "Término (linha de base)": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
        },
    )
    st.caption(
        t("🟪 Roxo = tarefa crítica · 🟥 Vermelho = atrasada · Vermelho mais forte = crítica e atrasada.", idioma)
    )
    st.download_button(
        t("⬇️ Baixar relatório de tarefas (Excel)", idioma),
        data=gerar_excel_tabela(tabela, "Tarefas"),
        file_name=f"tarefas_{projeto.nome.strip().replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()
    st.subheader(t("Planejado x Executado por período", idioma))

    datas_periodo = []
    for tarefa in projeto.tarefas_detalhe:
        datas_periodo += [tarefa.inicio, tarefa.termino, tarefa.inicio_real, tarefa.termino_real]
    datas_periodo = [d for d in datas_periodo if d is not None]

    if not datas_periodo:
        st.info(t("Não há datas suficientes no arquivo para montar o filtro por período.", idioma))
    else:
        data_min_tarefas = min(datas_periodo)
        data_max_tarefas = max(datas_periodo)

        _versao = st.session_state["periodo_versao"]
        _g_inicio, _g_fim = obter_periodo_global()
        _tarefas_inicio = max(_g_inicio, data_min_tarefas)
        _tarefas_fim = min(_g_fim, data_max_tarefas)
        if _tarefas_inicio > _tarefas_fim:
            _tarefas_inicio, _tarefas_fim = data_min_tarefas, data_max_tarefas
        _chave_tarefas = f"tarefas_periodo_v{_versao}"

        def _on_change_tarefas_periodo(_chave=_chave_tarefas):
            valor = st.session_state[_chave]
            if isinstance(valor, (tuple, list)) and len(valor) == 2:
                definir_periodo_global(valor[0], valor[1])

        periodo_tarefas = st.date_input(
            t("Filtrar por data", idioma),
            value=(_tarefas_inicio, _tarefas_fim),
            min_value=data_min_tarefas,
            max_value=data_max_tarefas,
            key=_chave_tarefas,
            on_change=_on_change_tarefas_periodo,
            format=formato_coluna_data(idioma),
        )
        if isinstance(periodo_tarefas, (tuple, list)) and len(periodo_tarefas) == 2:
            periodo_inicio, periodo_fim = periodo_tarefas
        else:
            periodo_inicio, periodo_fim = data_min_tarefas, data_max_tarefas

        def _sobrepoe_periodo(inicio, fim):
            if inicio is None or fim is None:
                return False
            return inicio <= periodo_fim and fim >= periodo_inicio

        tarefas_planejadas = [
            t for t in projeto.tarefas_detalhe if _sobrepoe_periodo(t.inicio, t.termino)
        ]
        tarefas_executadas = [
            t for t in projeto.tarefas_detalhe if _sobrepoe_periodo(t.inicio_real, t.termino_real)
        ]

        def _tabela_periodo(lista):
            return pd.DataFrame(
                [
                    {
                        "Tarefa": t.nome,
                        "Início": t.inicio,
                        "Término": t.termino,
                        "Início Real": t.inicio_real,
                        "Término Real": t.termino_real,
                        "% Concluído": t.percentual_concluido,
                        "Crítica": "Sim" if t.critica else "Não",
                    }
                    for t in lista
                ]
            )

        df_planejadas = _tabela_periodo(tarefas_planejadas)
        df_executadas = _tabela_periodo(tarefas_executadas)
        sufixo_periodo = f"{periodo_inicio}_a_{periodo_fim}"

        col_plan, col_exec = st.columns(2)
        with col_plan:
            st.markdown(f"**{tf('Planejadas no período ({n})', idioma, n=len(tarefas_planejadas))}**")
            st.caption(t("Tarefas cujo cronograma atual (Início/Término vigentes) cruza o período selecionado.", idioma))
            st.dataframe(
                df_planejadas,
                hide_index=True,
                width="stretch",
                column_config={
                    "Início": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                    "Término": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                    "Início Real": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                    "Término Real": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                },
            )
            st.download_button(
                t("⬇️ Baixar planejadas (Excel)", idioma),
                data=gerar_excel_tabela(df_planejadas, "Planejadas"),
                file_name=f"planejadas_{sufixo_periodo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with col_exec:
            st.markdown(f"**{tf('Executadas no período ({n})', idioma, n=len(tarefas_executadas))}**")
            st.caption(t("Tarefas com Início Real e Término Real registrados (já concluídas) que cruzam o período selecionado.", idioma))
            st.dataframe(
                df_executadas,
                hide_index=True,
                width="stretch",
                column_config={
                    "Início": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                    "Término": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                    "Início Real": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                    "Término Real": st.column_config.DateColumn(format=formato_coluna_data(idioma)),
                },
            )
            st.download_button(
                t("⬇️ Baixar executadas (Excel)", idioma),
                data=gerar_excel_tabela(df_executadas, "Executadas"),
                file_name=f"executadas_{sufixo_periodo}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

with aba_gantt:
    st.subheader(t("Gráfico de Gantt", idioma))

    col_g1, col_g2, col_g3 = st.columns([2, 1, 1])
    busca_gantt = col_g1.text_input(t("Buscar tarefa pelo nome", idioma), key="gantt_busca")
    somente_criticas_gantt = col_g2.checkbox(t("Somente críticas", idioma), key="gantt_criticas")
    somente_atrasadas_gantt = col_g3.checkbox(t("Somente atrasadas", idioma), key="gantt_atrasadas")

    tarefas_com_data = [t for t in projeto.tarefas_detalhe if t.inicio and t.termino]

    if tarefas_com_data:
        data_min_gantt = min(t.inicio for t in tarefas_com_data)
        data_max_gantt = max(t.termino for t in tarefas_com_data)

        _versao = st.session_state["periodo_versao"]
        _g_inicio, _g_fim = obter_periodo_global()
        _gantt_inicio = max(_g_inicio, data_min_gantt)
        _gantt_fim = min(_g_fim, data_max_gantt)
        if _gantt_inicio > _gantt_fim:
            _gantt_inicio, _gantt_fim = data_min_gantt, data_max_gantt
        _chave_gantt = f"gantt_periodo_v{_versao}"

        def _on_change_gantt_periodo(_chave=_chave_gantt):
            p = st.session_state[_chave]
            if isinstance(p, (tuple, list)) and len(p) == 2:
                definir_periodo_global(p[0], p[1])

        periodo_gantt = st.date_input(
            t("Filtrar por data (Início/Término cruzando o período)", idioma),
            value=(_gantt_inicio, _gantt_fim),
            min_value=data_min_gantt,
            max_value=data_max_gantt,
            key=_chave_gantt,
            on_change=_on_change_gantt_periodo,
            format=formato_coluna_data(idioma),
        )
        if isinstance(periodo_gantt, (tuple, list)) and len(periodo_gantt) == 2:
            filtro_data_inicio, filtro_data_fim = periodo_gantt
        else:
            filtro_data_inicio, filtro_data_fim = data_min_gantt, data_max_gantt
    else:
        filtro_data_inicio, filtro_data_fim = None, None

    tarefas_gantt = tarefas_com_data
    if busca_gantt:
        tarefas_gantt = [t for t in tarefas_gantt if busca_gantt.lower() in t.nome.lower()]
    if somente_criticas_gantt:
        tarefas_gantt = [t for t in tarefas_gantt if t.critica]
    if somente_atrasadas_gantt:
        tarefas_gantt = [t for t in tarefas_gantt if t.atrasada]
    if filtro_data_inicio and filtro_data_fim:
        tarefas_gantt = [
            t for t in tarefas_gantt if t.inicio <= filtro_data_fim and t.termino >= filtro_data_inicio
        ]

    def t_(texto):
        return t(texto, idioma)

    def _status_tarefa(t):
        if t.percentual_concluido >= 100:
            return t_("Concluída")
        if t.atrasada and t.critica:
            return t_("Crítica atrasada")
        if t.atrasada:
            return t_("Atrasada")
        if t.critica:
            return t_("Crítica")
        return t_("No prazo")

    cores_status = {
        t_("Concluída"): "#2E8B57",
        t_("No prazo"): "#5B8DB8",
        t_("Crítica"): "#4A235A",
        t_("Atrasada"): "#E67E22",
        t_("Crítica atrasada"): "#C0392B",
    }

    if not tarefas_gantt:
        st.info(t("Nenhuma tarefa encontrada com os filtros selecionados (ou sem datas de início/término).", idioma))
    else:
        barras = [t for t in tarefas_gantt if not t.marco]
        marcos_gantt = [t for t in tarefas_gantt if t.marco]

        col_tarefa_gantt = t("Tarefa", idioma)
        col_inicio_gantt = t("Início", idioma)
        col_termino_gantt = t("Término", idioma)
        col_status_gantt = t("Status", idioma)
        col_pct_gantt = t("% Concluído", idioma)

        if barras:
            df_barras = pd.DataFrame(
                [
                    {
                        col_tarefa_gantt: f"{t.id} - {t.nome}",
                        col_inicio_gantt: t.inicio,
                        col_termino_gantt: t.termino,
                        col_status_gantt: _status_tarefa(t),
                        col_pct_gantt: t.percentual_concluido,
                    }
                    for t in barras
                ]
            )
            fig_gantt = px.timeline(
                df_barras,
                x_start=col_inicio_gantt,
                x_end=col_termino_gantt,
                y=col_tarefa_gantt,
                color=col_status_gantt,
                color_discrete_map=cores_status,
                hover_data=[col_pct_gantt],
                text=col_pct_gantt,
            )
            fig_gantt.update_traces(
                texttemplate="%{text:.0f}%",
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(size=11, color="white"),
            )
        else:
            fig_gantt = go.Figure()

        for status, cor in cores_status.items():
            marcos_status = [t for t in marcos_gantt if _status_tarefa(t) == status]
            if marcos_status:
                fig_gantt.add_trace(
                    go.Scatter(
                        x=[t.termino or t.inicio for t in marcos_status],
                        y=[f"{t.id} - {t.nome}" for t in marcos_status],
                        mode="markers",
                        marker=dict(symbol="diamond", size=13, color=cor, line=dict(width=1, color="white")),
                        name=tf("{status} (marco)", idioma, status=status),
                    )
                )

        todas_linhas_y = [f"{t.id} - {t.nome}" for t in barras + marcos_gantt]
        # Truque para duplicar o eixo de datas também no topo do gráfico: um marcador
        # invisível "ancora" o eixo x2, senão o Plotly não desenha seus rótulos.
        fig_gantt.add_trace(
            go.Scatter(
                x=[tarefas_gantt[0].inicio],
                y=[todas_linhas_y[0]],
                xaxis="x2",
                mode="markers",
                marker=dict(opacity=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )

        mapa_tarefa_visivel = {t.uid: t for t in tarefas_gantt}
        mapa_rotulo_visivel = {t.uid: rotulo for t, rotulo in zip(barras + marcos_gantt, todas_linhas_y)}
        for tarefa_dest in tarefas_gantt:
            for dep in tarefa_dest.dependencias:
                tarefa_orig = mapa_tarefa_visivel.get(dep.predecessora_uid)
                if tarefa_orig is None:
                    continue
                if dep.tipo == 0:
                    x_origem, x_destino = tarefa_orig.termino, tarefa_dest.termino
                elif dep.tipo == 2:
                    x_origem, x_destino = tarefa_orig.inicio, tarefa_dest.termino
                elif dep.tipo == 3:
                    x_origem, x_destino = tarefa_orig.inicio, tarefa_dest.inicio
                else:
                    x_origem, x_destino = tarefa_orig.termino, tarefa_dest.inicio
                fig_gantt.add_annotation(
                    x=x_destino,
                    y=mapa_rotulo_visivel[tarefa_dest.uid],
                    ax=x_origem,
                    ay=mapa_rotulo_visivel[tarefa_orig.uid],
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1,
                    arrowcolor="rgba(190,190,190,0.55)",
                    text="",
                )

        if data_status:
            fig_gantt.add_vline(
                x=pd.Timestamp(data_status),
                line_dash="dot",
                line_color="#DDDDDD",
                annotation_text=t("Data de status", idioma),
                annotation_position="bottom right",
            )

        total_linhas = len(barras) + len(marcos_gantt)
        fig_gantt.update_yaxes(autorange="reversed", title="", showgrid=True, gridcolor="rgba(128,128,128,0.15)")
        fig_gantt.update_xaxes(
            title=t("Data", idioma),
            showgrid=True,
            gridcolor="rgba(128,128,128,0.25)",
            side="bottom",
        )
        fig_gantt.update_layout(
            height=max(450, 30 * total_linhas),
            legend_title_text=col_status_gantt,
            bargap=0.3,
            xaxis2=dict(overlaying="x", matches="x", side="top", showticklabels=True, showgrid=False),
            margin=dict(t=70),
        )
        st.plotly_chart(fig_gantt, width="stretch")
        st.caption(
            tf(
                "Exibindo {n} tarefa(s). Losangos representam marcos; o número dentro das barras é o % concluído. "
                "Setas cinzas indicam dependências entre tarefas (só aparecem quando predecessora e sucessora estão "
                "ambas visíveis com os filtros atuais). Use os filtros acima para reduzir a lista em projetos grandes.",
                idioma,
                n=total_linhas,
            )
        )

        mapa_id_global = {t.uid: t.id for t in projeto.tarefas_detalhe}
        df_relatorio_gantt = pd.DataFrame(
            [
                {
                    "ID": t.id,
                    "Tarefa": t.nome,
                    "Início": t.inicio,
                    "Término": t.termino,
                    "Marco": "Sim" if t.marco else "Não",
                    "Status": _status_tarefa(t),
                    "% Concluído": t.percentual_concluido,
                    "Predecessoras": ", ".join(
                        str(mapa_id_global.get(d.predecessora_uid, d.predecessora_uid)) for d in t.dependencias
                    ),
                }
                for t in tarefas_gantt
            ]
        )
        st.download_button(
            t("⬇️ Baixar relatório do Gantt (Excel)", idioma),
            data=gerar_excel_tabela(df_relatorio_gantt, "Gantt"),
            file_name=f"gantt_{projeto.nome.strip().replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

with aba_checklist:
    st.subheader(t("Checklist de Qualidade do Cronograma", idioma))
    st.caption(
        t("Itens avaliados automaticamente a partir dos dados do arquivo.", idioma)
    )

    itens_checklist = avaliar_checklist(projeto, indicadores, idioma=idioma)
    resultado_checklist = calcular_pontuacao(itens_checklist)

    c1, c2, c3 = st.columns(3)
    c1.metric(t("Pontuação", idioma), f"{resultado_checklist['pontos']} / {resultado_checklist['maximo']}")
    c2.metric(t("Percentual", idioma), f"{resultado_checklist['percentual']:.1f}%")
    c3.metric(t("Maturidade", idioma), t(resultado_checklist["classificacao"], idioma))
    st.progress(min(resultado_checklist["percentual"] / 100, 1.0))
    st.caption(
        tf(
            "{avaliados} de {total} itens contam na pontuação.",
            idioma,
            avaliados=resultado_checklist["itens_avaliados"],
            total=resultado_checklist["total_itens"],
        )
    )

    with st.expander(t("Tabela de classificação de maturidade", idioma)):
        st.table(
            pd.DataFrame(
                {
                    t("Pontuação", idioma): ["95–100%", "85–94%", "70–84%", "50–69%", t("Abaixo de 50%", idioma)],
                    t("Maturidade", idioma): [
                        t("Excelente", idioma),
                        t("Muito bom", idioma),
                        t("Adequado, com melhorias", idioma),
                        t("Baixa maturidade", idioma),
                        t("Cronograma inadequado para controle", idioma),
                    ],
                }
            )
        )

    icones_status = {"Conforme": "✅", "Parcial": "⚠️", "Não Conforme": "❌", "N/A": "➖"}

    secoes_checklist: dict[str, list] = {}
    for item in itens_checklist:
        secoes_checklist.setdefault(item.secao, []).append(item)

    for secao, itens_secao in secoes_checklist.items():
        with st.expander(secao):
            for item in itens_secao:
                st.markdown(f"{icones_status.get(item.status, '➖')} {item.texto}")
                if item.evidencia:
                    st.caption(item.evidencia)

    st.divider()
    df_checklist = pd.DataFrame(
        [
            {
                "Seção": item.secao,
                "Item": item.texto,
                "Status": item.status,
                "Evidência": item.evidencia,
            }
            for item in itens_checklist
        ]
    )
    st.download_button(
        t("⬇️ Baixar checklist (Excel)", idioma),
        data=gerar_excel_tabela(df_checklist, "Checklist"),
        file_name=f"checklist_{projeto.nome.strip().replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with aba_recursos:
    st.subheader(t("Recursos", idioma))
    df_recursos = tabela_recursos(projeto)
    if df_recursos.empty:
        st.info(t("O arquivo não contém informações de recursos.", idioma))
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            st.dataframe(df_recursos, hide_index=True, width="stretch")
        with col_b:
            if indicadores.unidade == "R$":
                coluna_grafico, titulo_grafico, eixo_grafico = "Custo", t("Custo por Recurso", idioma), t("Custo (R$)", idioma)
            else:
                coluna_grafico, titulo_grafico, eixo_grafico = "Trabalho (horas)", t("Trabalho por Recurso", idioma), t("Horas", idioma)
            fig_recursos = go.Figure(
                go.Bar(x=df_recursos["Recurso"], y=df_recursos[coluna_grafico], marker_color="#5B8DB8")
            )
            fig_recursos.update_layout(title=titulo_grafico, yaxis_title=eixo_grafico, height=420)
            st.plotly_chart(fig_recursos, width="stretch")

with aba_exportar:
    st.subheader(t("Exportar Relatórios", idioma))
    st.write(t("Gere um relatório com o resumo, indicadores, tarefas e a curva S do projeto.", idioma))

    nome_base = projeto.nome.strip().replace(" ", "_") or "cronograma"
    carimbo = datetime.now().strftime("%Y%m%d_%H%M")

    col_x, col_p = st.columns(2)
    with col_x:
        excel_bytes = gerar_excel(projeto, indicadores, curva)
        st.download_button(
            t("⬇️ Baixar Excel", idioma),
            data=excel_bytes,
            file_name=f"relatorio_{nome_base}_{carimbo}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with col_p:
        pdf_bytes = gerar_pdf(projeto, indicadores, percepcoes_exportacao, curva)
        st.download_button(
            t("⬇️ Baixar PDF", idioma),
            data=pdf_bytes,
            file_name=f"relatorio_{nome_base}_{carimbo}.pdf",
            mime="application/pdf",
            width="stretch",
        )

    st.divider()
    st.subheader(t("Relatório Executivo por Período", idioma))
    st.write(
        t(
            "Gere um PDF pronto para apresentação com os indicadores, a Curva S, o Gráfico de Gantt "
            "e a lista de atividades filtrados por um período específico.",
            idioma,
        )
    )

    if tarefas_com_data:
        _versao = st.session_state["periodo_versao"]
        _g_inicio, _g_fim = obter_periodo_global()
        _exec_inicio = max(_g_inicio, data_min_gantt)
        _exec_fim = min(_g_fim, data_max_gantt)
        if _exec_inicio > _exec_fim:
            _exec_inicio, _exec_fim = data_min_gantt, data_max_gantt
        _chave_exec = f"periodo_exec_v{_versao}"

        def _on_change_periodo_exec(_chave=_chave_exec):
            p = st.session_state[_chave]
            if isinstance(p, (tuple, list)) and len(p) == 2:
                definir_periodo_global(p[0], p[1])

        periodo_exec = st.date_input(
            t("Selecione o período do relatório", idioma),
            value=(_exec_inicio, _exec_fim),
            min_value=data_min_gantt,
            max_value=data_max_gantt,
            key=_chave_exec,
            on_change=_on_change_periodo_exec,
            format=formato_coluna_data(idioma),
        )
        if isinstance(periodo_exec, (tuple, list)) and len(periodo_exec) == 2:
            periodo_exec_inicio, periodo_exec_fim = periodo_exec
        else:
            periodo_exec_inicio, periodo_exec_fim = data_min_gantt, data_max_gantt

        tarefas_periodo_exec = [
            t
            for t in tarefas_com_data
            if t.inicio <= periodo_exec_fim and t.termino >= periodo_exec_inicio
        ]
        curva_periodo_exec = curva.loc[
            pd.Timestamp(periodo_exec_inicio) : pd.Timestamp(periodo_exec_fim)
        ][["Linha de Base", "Realizado / Previsto"]]

        st.caption(tf("{n} tarefa(s) encontradas no período selecionado.", idioma, n=len(tarefas_periodo_exec)))

        pdf_executivo = gerar_pdf_executivo(
            projeto,
            indicadores,
            curva_periodo_exec,
            tarefas_periodo_exec,
            periodo_exec_inicio,
            periodo_exec_fim,
            data_status,
        )
        st.download_button(
            t("⬇️ Baixar Relatório Executivo (PDF)", idioma),
            data=pdf_executivo,
            file_name=f"executivo_{nome_base}_{periodo_exec_inicio}_a_{periodo_exec_fim}.pdf",
            mime="application/pdf",
            width="stretch",
        )
    else:
        st.info(t("Não há tarefas com datas suficientes para gerar o relatório executivo.", idioma))
