"""Testes de integração do app Streamlit via streamlit.testing.v1.AppTest.

Cada teste sobe o app de verdade (sem navegador), envia arquivos pelo uploader
e verifica que nenhuma exceção ocorre e que os elementos esperados aparecem.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
APP = str(RAIZ / "app.py")
TIMEOUT = 90


def _ler(caminho: Path) -> bytes:
    return caminho.read_bytes()


@pytest.fixture()
def app():
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    return at


def _upload(at: AppTest, nome: str, conteudo: bytes) -> AppTest:
    at.sidebar.file_uploader[0].upload(nome, conteudo, "text/xml")
    at.run(timeout=TIMEOUT)
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_sem_arquivo_mostra_instrucao(app):
    assert app.title[0].value.startswith("📊")


def test_upload_projeto_com_custo(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    assert "Implantação ERP" in app.title[0].value
    # Com custo e sem coluna de peso: seletor Custo/Duração deve aparecer.
    rotulos = [sb.label for sb in app.sidebar.selectbox]
    assert any("Curva S" in r for r in rotulos)


def test_upload_sem_custo_nao_mostra_seletor(app):
    _upload(app, "sem_custo.xml", _ler(RAIZ / "exemplo_sem_custo.xml"))
    rotulos = [sb.label for sb in app.sidebar.selectbox]
    assert not any("Curva S" in r for r in rotulos)


def test_aba_status_reuniao(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    aba = app.tabs[1]
    rotulos_metricas = {m.label for m in aba.metric}
    assert {"% Concluído", "SPI", "CPI", "Atraso", "Críticas Atrasadas"} <= rotulos_metricas
    assert {"Otimista", "Realista", "Pessimista"} <= rotulos_metricas
    textos_markdown = " ".join(m.value for m in aba.markdown)
    assert "riscos" in textos_markdown.lower()
    assert "marcos" in textos_markdown.lower()
    assert "recomendações" in textos_markdown.lower()
    assert "matriz de risco" in textos_markdown.lower()
    # Este cronograma tem tarefas críticas atrasadas, então pelo menos uma recomendação
    # (renderizada como st.info) deve aparecer.
    assert aba.info
    rotulos_botoes = [db.label for db in aba.download_button]
    assert any("Status de Reunião" in r and "PDF" in r for r in rotulos_botoes)


def test_aba_simulacao(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    aba = app.tabs[2]
    assert aba.dataframe  # a tabela de tarefas com a coluna de checkbox "Concluir (100%)"
    colunas = aba.dataframe[0].value.columns
    assert {
        "concluir", "tarefa", "critica", "percentual",
        "inicio_atual", "termino_atual", "inicio_planejado", "termino_planejado",
    } <= set(colunas)
    rotulos_metricas = {m.label for m in aba.metric}
    assert {"% Concluído", "SPI", "CPI", "Forecast Término"} <= rotulos_metricas


def test_simulacao_filtro_criticas_e_marcos(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    aba = app.tabs[2]
    # Sem o filtro: todas as tarefas não concluídas aparecem, inclusive marcos e não críticas.
    tarefas_sem_filtro = list(aba.dataframe[0].value["tarefa"])
    assert "Testes de Aceitação" in tarefas_sem_filtro
    assert "Go-Live" in tarefas_sem_filtro

    aba.checkbox[0].set_value(True).run(timeout=TIMEOUT)
    assert not app.exception

    # Com o filtro: só tarefas críticas e marcos permanecem ('Testes de Aceitação' não é
    # crítica nem marco, então some da lista); 'Go-Live' (marco) continua aparecendo.
    aba_filtrada = app.tabs[2]
    tarefas_com_filtro = list(aba_filtrada.dataframe[0].value["tarefa"])
    assert "Go-Live" in tarefas_com_filtro
    assert "Testes de Aceitação" not in tarefas_com_filtro


def test_simulacao_marcar_tarefa_concluida_aumenta_percentual(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    aba = app.tabs[2]
    df_tarefas = aba.dataframe[0].value
    # 'Testes de Aceitação' está 0% concluída no exemplo — marcar como concluída
    # garante uma mudança real no % Concluído do projeto.
    indice_testes = int(df_tarefas.index[df_tarefas["tarefa"] == "Testes de Aceitação"][0])
    percentual_antes = next(m for m in aba.metric if m.label == "% Concluído").value

    chave_editor = aba.dataframe[0].key
    app.session_state[chave_editor] = {
        "edited_rows": {indice_testes: {"concluir": True}},
        "added_rows": [],
        "deleted_rows": [],
    }
    app.run(timeout=TIMEOUT)
    assert not app.exception

    aba_depois = app.tabs[2]
    percentual_depois = next(m for m in aba_depois.metric if m.label == "% Concluído").value
    assert percentual_depois != percentual_antes

    # 'exemplo_cronograma.xml' não tem vínculos entre tarefas (PredecessorLink), então a
    # observação deve cair no caso "nenhuma outra tarefa depende diretamente dela".
    textos_caption = " ".join(c.value for c in aba_depois.caption)
    assert "Testes de Aceitação" in textos_caption
    assert "nenhuma outra tarefa depende diretamente dela" in textos_caption


def test_simulacao_sem_selecao_nao_mostra_observacoes(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    aba = app.tabs[2]
    textos_markdown = " ".join(m.value for m in aba.markdown)
    assert "Observações" not in textos_markdown


def test_seletor_peso_editado(app):
    _upload(app, "com_peso.xml", _ler(RAIZ / "tests/fixtures/cronograma_com_peso.xml"))
    seletor = next(sb for sb in app.sidebar.selectbox if "Curva S" in sb.label)
    assert seletor.options == ["Duração", "Peso da coluna 'Peso'"]
    seletor.set_value("Peso da coluna 'Peso'").run(timeout=TIMEOUT)
    assert not app.exception


def test_portfolio_com_dois_arquivos(app):
    app.sidebar.file_uploader[0].upload("a.xml", _ler(RAIZ / "exemplo_cronograma.xml"), "text/xml")
    app.sidebar.file_uploader[0].upload("b.xml", _ler(RAIZ / "exemplo_sem_custo.xml"), "text/xml")
    app.run(timeout=TIMEOUT)
    assert not app.exception
    assert "Portfólio" in app.title[0].value
    # Portfólio com custo em pelo menos um projeto: seletor de método na área principal.
    rotulos = [sb.label for sb in app.selectbox]
    assert any("portfólio" in r.lower() for r in rotulos)


def test_remocao_de_arquivo_limpa_estado(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    app.sidebar.file_uploader[0].clear()
    app.run(timeout=TIMEOUT)
    assert not app.exception
    assert app.session_state["projetos"] == {}


def test_idioma_ingles(app):
    app.sidebar.segmented_control[0].set_value("English").run(timeout=TIMEOUT)
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    rotulos = [sb.label for sb in app.sidebar.selectbox]
    assert any("S-Curve" in r for r in rotulos)


def test_download_buttons_presentes(app):
    _upload(app, "exemplo.xml", _ler(RAIZ / "exemplo_cronograma.xml"))
    rotulos = [db.label for db in app.download_button]
    assert any("Excel" in r for r in rotulos)
    assert any("PDF" in r for r in rotulos)
