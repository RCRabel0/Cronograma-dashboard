"""Leitor de arquivos .ccx — formato do Concerto (ProChain Solutions), uma ferramenta
de Corrente Crítica (CCPM) que se integra ao MS Project.

Um .ccx é um arquivo zip contendo, entre outros: o cronograma original em .mpp (só um
template vazio nos arquivos observados — o Concerto não mantém os dados reais nele) e
um arquivo .cpd, que por sua vez **não é um formato proprietário**: é um banco de dados
Microsoft Access (Jet/MDB) usando o mesmo schema que o MS Project gera na opção
"Salvar como > Banco de dados de projeto" — tabelas MSP_PROJECTS, MSP_TASKS, MSP_LINKS,
MSP_RESOURCES, MSP_ASSIGNMENTS.

Este leitor extrai o .cpd do zip e lê essas tabelas diretamente via ODBC (pyodbc +
driver "Microsoft Access Driver (*.mdb, *.accdb)").

Limitações conhecidas:
- Exige Windows com o driver ODBC do Access instalado (Access, Office, ou o pacote
  redistribuível "Microsoft Access Database Engine") — diferente do suporte a .mpp
  (via MPXJ/Java), isso não funciona em outros sistemas operacionais nem em nuvem.
- Não lê colunas de peso/campo personalizado (o equivalente ao 'peso_editado' dos
  outros leitores) — os projetos Concerto observados não usam esse recurso.
- O tipo de vínculo (LINK_TYPE) é assumido na mesma numeração do MSPDI (0=Término-
  Término, 1=Término-Início, 2=Início-Término, 3=Início-Início) usada no resto do
  programa; só foi possível confirmar empiricamente o valor 1 (Término-Início, o mais
  comum) contra um arquivo real — os demais não foram verificados por falta de uma
  amostra com esses tipos de vínculo.
"""

import os
import tempfile
import zipfile
from datetime import date, datetime
from typing import Optional

from .leitor_xml import ArquivoInvalidoError
from .modelos import Dependencia, Projeto, Recurso, Tarefa

# TASK_DUR, TASK_BASE_DUR, TASK_ACT_DUR, TASK_TOTAL_SLACK e os campos de trabalho
# (*_WORK) do schema MSP_* são armazenados em décimos de minuto.
_DECIMINUTOS_POR_HORA = 600.0


def _driver_disponivel() -> bool:
    try:
        import pyodbc
    except ImportError:
        return False
    try:
        return any("access" in d.lower() for d in pyodbc.drivers())
    except Exception:
        return False


class DriverAccessIndisponivelError(Exception):
    """O suporte a .ccx requer o driver ODBC do Microsoft Access (Windows)."""


def _data(valor: Optional[datetime]) -> Optional[date]:
    return valor.date() if valor is not None else None


def _horas(valor, divisor: float = _DECIMINUTOS_POR_HORA) -> float:
    return (valor or 0) / divisor


def _extrair_cpd(caminho_ccx: str) -> bytes:
    try:
        with zipfile.ZipFile(caminho_ccx) as zf:
            nomes_cpd = [nome for nome in zf.namelist() if nome.lower().endswith(".cpd")]
            if not nomes_cpd:
                raise ArquivoInvalidoError(
                    "O arquivo .ccx não contém os dados do projeto (.cpd) dentro dele "
                    "— formato inesperado."
                )
            return zf.read(nomes_cpd[0])
    except zipfile.BadZipFile as e:
        raise ArquivoInvalidoError(f"O arquivo .ccx não é um arquivo zip válido: {e}") from e


def ler_ccx(caminho: str) -> Projeto:
    if not _driver_disponivel():
        raise DriverAccessIndisponivelError(
            "Não foi possível ler o arquivo .ccx: é necessário o driver ODBC do "
            "Microsoft Access instalado (só disponível no Windows, com o Access ou o "
            "'Microsoft Access Database Engine' instalado)."
        )

    import pyodbc

    conteudo_cpd = _extrair_cpd(caminho)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mdb") as tmp:
        tmp.write(conteudo_cpd)
        caminho_mdb_temporario = tmp.name

    try:
        conn_str = (
            r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + caminho_mdb_temporario
        )
        try:
            conexao = pyodbc.connect(conn_str, autocommit=True)
        except pyodbc.Error as e:
            raise ArquivoInvalidoError(f"Não foi possível abrir os dados do arquivo .ccx: {e}") from e

        try:
            return _ler_projeto(conexao)
        finally:
            conexao.close()
    finally:
        try:
            os.unlink(caminho_mdb_temporario)
        except PermissionError:
            pass


def _ler_projeto(conexao) -> Projeto:
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT PROJ_NAME, PROJ_PROP_TITLE, PROJ_INFO_STATUS_DATE FROM MSP_PROJECTS"
    )
    linha_projeto = cursor.fetchone()
    if linha_projeto is None:
        raise ArquivoInvalidoError("O arquivo .ccx não contém informações de projeto (MSP_PROJECTS vazia).")
    nome_proj, titulo_proj, status_proj = linha_projeto
    # PROJ_NAME normalmente traz o nome real do projeto; PROJ_PROP_TITLE nos arquivos
    # do Concerto observados vinha preenchido com um valor de template
    # ('Concerto_Global_Default'), por isso a ordem de preferência é essa.
    nome = nome_proj or titulo_proj or "Projeto"

    cursor.execute(
        "SELECT TASK_UID, TASK_ID, TASK_NAME, TASK_OUTLINE_LEVEL, TASK_IS_SUMMARY, "
        "TASK_IS_MILESTONE, TASK_IS_CRITICAL, TASK_PCT_COMP, TASK_START_DATE, TASK_FINISH_DATE, "
        "TASK_BASE_START, TASK_BASE_FINISH, TASK_ACT_START, TASK_ACT_FINISH, "
        "TASK_DUR, TASK_BASE_DUR, TASK_ACT_DUR, TASK_COST, TASK_BASE_COST, TASK_ACT_COST, "
        "TASK_CONSTRAINT_TYPE, TASK_TOTAL_SLACK, TASK_WBS "
        "FROM MSP_TASKS WHERE TASK_ID IS NOT NULL AND TASK_UID <> 0 ORDER BY TASK_ID"
    )
    tarefas: list[Tarefa] = []
    for linha in cursor.fetchall():
        (
            uid, id_, nome_tarefa, nivel, resumo, marco, critica, pct,
            inicio, termino, base_inicio, base_termino, real_inicio, real_termino,
            dur, base_dur, real_dur, custo, base_custo, real_custo,
            restricao, folga, wbs,
        ) = linha
        tarefas.append(
            Tarefa(
                uid=str(uid),
                id=id_ if id_ is not None else uid,
                nome=nome_tarefa or "",
                nivel_esquema=nivel or 0,
                resumo=bool(resumo),
                marco=bool(marco),
                critica=bool(critica),
                percentual_concluido=float(pct or 0),
                inicio=_data(inicio),
                termino=_data(termino),
                inicio_linha_base=_data(base_inicio),
                termino_linha_base=_data(base_termino),
                inicio_real=_data(real_inicio),
                termino_real=_data(real_termino),
                duracao_horas=_horas(dur),
                duracao_linha_base_horas=_horas(base_dur),
                duracao_real_horas=_horas(real_dur),
                custo=float(custo or 0),
                custo_linha_base=float(base_custo or 0),
                custo_real=float(real_custo or 0),
                tipo_restricao=int(restricao) if restricao is not None else 0,
                folga_horas=_horas(folga) if folga is not None else None,
                wbs=wbs or "",
            )
        )

    tarefas_por_uid = {t.uid: t for t in tarefas}

    cursor.execute("SELECT LINK_PRED_UID, LINK_SUCC_UID, LINK_TYPE FROM MSP_LINKS")
    for pred_uid, succ_uid, tipo in cursor.fetchall():
        tarefa_sucessora = tarefas_por_uid.get(str(succ_uid))
        if tarefa_sucessora is not None and str(pred_uid) in tarefas_por_uid:
            tarefa_sucessora.dependencias.append(
                Dependencia(predecessora_uid=str(pred_uid), tipo=int(tipo) if tipo is not None else 1)
            )

    cursor.execute("SELECT RES_UID, RES_NAME, RES_WORK, RES_COST FROM MSP_RESOURCES WHERE RES_NAME IS NOT NULL")
    recursos: list[Recurso] = []
    nomes_recurso_por_uid: dict[str, str] = {}
    for uid, nome_recurso, trabalho, custo in cursor.fetchall():
        recursos.append(
            Recurso(uid=str(uid), nome=nome_recurso, trabalho_horas=_horas(trabalho), custo=float(custo or 0))
        )
        nomes_recurso_por_uid[str(uid)] = nome_recurso

    cursor.execute("SELECT TASK_UID, RES_UID FROM MSP_ASSIGNMENTS")
    for task_uid, res_uid in cursor.fetchall():
        tarefa = tarefas_por_uid.get(str(task_uid))
        nome_recurso = nomes_recurso_por_uid.get(str(res_uid))
        if tarefa is not None and nome_recurso is not None:
            tarefa.recursos.append(nome_recurso)

    numero_baselines_salvas = 1 if any(t.termino_linha_base is not None for t in tarefas) else 0

    # PROJ_INFO_START_DATE/FINISH_DATE em arquivos do Concerto observados vinham com
    # valores de template (não o período real do projeto) — o início/término do
    # projeto são derivados diretamente das próprias tarefas, como o resto do
    # programa já faz em outros lugares (ex.: filtro de período global no app.py).
    tarefas_com_data = [t for t in tarefas_por_uid.values() if not t.resumo and t.inicio and t.termino]
    inicio_derivado = min((t.inicio for t in tarefas_com_data), default=None)
    termino_derivado = max((t.termino for t in tarefas_com_data), default=None)

    return Projeto(
        nome=nome,
        inicio=inicio_derivado,
        termino=termino_derivado,
        data_status=_data(status_proj),
        numero_baselines_salvas=numero_baselines_salvas,
        tarefas=tarefas,
        recursos=recursos,
    )
