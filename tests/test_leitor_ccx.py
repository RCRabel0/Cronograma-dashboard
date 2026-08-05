import zipfile
from pathlib import Path

import pytest

from cronograma import leitor_ccx
from cronograma.leitor_ccx import DriverAccessIndisponivelError, ler_ccx
from cronograma.leitor_xml import ArquivoInvalidoError

RAIZ = Path(__file__).resolve().parent.parent


def _arquivo_ccx_real() -> Path | None:
    candidatos = sorted(RAIZ.glob("*.ccx"))
    return candidatos[0] if candidatos else None


def test_ler_ccx_sem_driver_levanta_erro_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(leitor_ccx, "_driver_disponivel", lambda: False)
    with pytest.raises(DriverAccessIndisponivelError):
        ler_ccx(str(tmp_path / "qualquer.ccx"))


def test_extrair_cpd_arquivo_nao_e_zip(tmp_path):
    caminho = tmp_path / "invalido.ccx"
    caminho.write_bytes(b"nao e um zip")
    with pytest.raises(ArquivoInvalidoError):
        leitor_ccx._extrair_cpd(str(caminho))


def test_extrair_cpd_zip_sem_cpd(tmp_path):
    caminho = tmp_path / "sem_cpd.ccx"
    with zipfile.ZipFile(caminho, "w") as zf:
        zf.writestr("projeto.mpp", b"conteudo qualquer")
    with pytest.raises(ArquivoInvalidoError):
        leitor_ccx._extrair_cpd(str(caminho))


@pytest.mark.skipif(
    not leitor_ccx._driver_disponivel(),
    reason="requer o driver ODBC do Microsoft Access instalado (Windows)",
)
@pytest.mark.skipif(
    _arquivo_ccx_real() is None,
    reason="requer um arquivo .ccx real na raiz do projeto para o teste de integração",
)
def test_ler_ccx_arquivo_real():
    projeto = ler_ccx(str(_arquivo_ccx_real()))
    assert projeto.nome
    assert "Concerto_Global_Default" not in projeto.nome
    assert projeto.inicio is not None
    assert projeto.termino is not None
    assert projeto.inicio <= projeto.termino
    assert len(projeto.tarefas) > 0
    assert len(projeto.tarefas_detalhe) > 0
    # As datas do projeto devem vir das próprias tarefas, não de um placeholder do
    # Concerto (que nos arquivos observados usava datas de 2008/2015 incompatíveis).
    tarefas_com_termino = [t for t in projeto.tarefas_detalhe if t.termino]
    assert projeto.termino == max(t.termino for t in tarefas_com_termino)
