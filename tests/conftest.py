import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cronograma.leitor_xml import ler_xml  # noqa: E402

ARQUIVO_COM_CUSTO = RAIZ / "exemplo_cronograma.xml"
ARQUIVO_SEM_CUSTO = RAIZ / "exemplo_sem_custo.xml"
ARQUIVO_COM_PESO = RAIZ / "tests" / "fixtures" / "cronograma_com_peso.xml"


@pytest.fixture(scope="session")
def projeto_com_custo():
    return ler_xml(str(ARQUIVO_COM_CUSTO))


@pytest.fixture(scope="session")
def projeto_sem_custo():
    return ler_xml(str(ARQUIVO_SEM_CUSTO))


@pytest.fixture(scope="session")
def projeto_com_peso():
    return ler_xml(str(ARQUIVO_COM_PESO))
