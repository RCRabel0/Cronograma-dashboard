from datetime import date

import pytest

from cronograma.leitor_xml import ArquivoInvalidoError, ler_xml


def test_le_dados_basicos(projeto_com_custo):
    p = projeto_com_custo
    assert p.nome == "Projeto Piloto - Implantação ERP"
    assert p.inicio == date(2026, 5, 1)
    assert p.termino == date(2026, 8, 15)
    assert p.data_status == date(2026, 7, 24)
    assert len(p.tarefas) == 5
    assert len(p.recursos) == 3


def test_tarefas_detalhe_exclui_resumos(projeto_com_custo):
    assert all(not t.resumo for t in projeto_com_custo.tarefas_detalhe)


def test_tem_custo(projeto_com_custo, projeto_sem_custo):
    assert projeto_com_custo.tem_custo
    assert not projeto_sem_custo.tem_custo


def test_marco_e_critica(projeto_com_custo):
    go_live = next(t for t in projeto_com_custo.tarefas if t.nome == "Go-Live")
    assert go_live.marco
    assert go_live.critica


def test_atrasada_por_baseline(projeto_com_custo):
    config = next(t for t in projeto_com_custo.tarefas if t.nome == "Configuração do Sistema")
    assert config.atrasada  # término 05/07 > baseline 25/06
    concluida = next(t for t in projeto_com_custo.tarefas if t.nome == "Levantamento de Requisitos")
    assert not concluida.atrasada  # 100% concluída nunca é atrasada


def test_recursos_atribuidos(projeto_com_custo):
    config = next(t for t in projeto_com_custo.tarefas if t.nome == "Configuração do Sistema")
    assert set(config.recursos) == {"Ana Souza", "Bruno Lima"}


def test_deteccao_coluna_peso(projeto_com_peso):
    p = projeto_com_peso
    assert p.nome_coluna_peso_editado == "Peso"
    assert p.tem_peso_editado
    pesos = {t.nome: t.peso_editado for t in p.tarefas_detalhe}
    assert pesos == {"Tarefa A": 80.0, "Tarefa B": 20.0}


def test_sem_coluna_peso(projeto_com_custo):
    assert projeto_com_custo.nome_coluna_peso_editado is None
    assert not projeto_com_custo.tem_peso_editado


def test_arquivo_invalido(tmp_path):
    caminho = tmp_path / "invalido.xml"
    caminho.write_text("isto não é XML", encoding="utf-8")
    with pytest.raises(ArquivoInvalidoError):
        ler_xml(str(caminho))


def test_xml_sem_tarefas(tmp_path):
    caminho = tmp_path / "vazio.xml"
    caminho.write_text(
        '<?xml version="1.0"?><Project xmlns="http://schemas.microsoft.com/project">'
        "<Name>X</Name></Project>",
        encoding="utf-8",
    )
    with pytest.raises(ArquivoInvalidoError):
        ler_xml(str(caminho))
