from datetime import date

from .modelos import Dependencia, Projeto, Recurso, Tarefa

_TIPO_RELACAO = {
    "FINISH_FINISH": 0,
    "FINISH_START": 1,
    "START_FINISH": 2,
    "START_START": 3,
}

_TIPO_RESTRICAO = {
    "AS_SOON_AS_POSSIBLE": 0,
    "AS_LATE_AS_POSSIBLE": 1,
    "MUST_START_ON": 2,
    "MUST_FINISH_ON": 3,
    "START_NO_EARLIER_THAN": 4,
    "START_NO_LATER_THAN": 5,
    "FINISH_NO_EARLIER_THAN": 6,
    "FINISH_NO_LATER_THAN": 7,
}

_HORAS_POR_UNIDADE = {
    "MINUTES": 1 / 60,
    "ELAPSED_MINUTES": 1 / 60,
    "HOURS": 1,
    "ELAPSED_HOURS": 1,
    "DAYS": 8,
    "ELAPSED_DAYS": 24,
    "WEEKS": 40,
    "ELAPSED_WEEKS": 168,
    "MONTHS": 160,
    "ELAPSED_MONTHS": 720,
}


class MpxjIndisponivelError(Exception):
    """O suporte a .mpp requer Java + a biblioteca mpxj instalados."""


def _para_data(ld) -> date | None:
    if ld is None:
        return None
    return date(ld.getYear(), ld.getMonthValue(), ld.getDayOfMonth())


def _duracao_para_horas(dur) -> float:
    if dur is None:
        return 0.0
    unidade = str(dur.getUnits())
    fator = _HORAS_POR_UNIDADE.get(unidade, 1)
    return float(dur.getDuration()) * fator


def _num(valor) -> float:
    if valor is None:
        return 0.0
    return float(valor)


def _manual(t) -> bool:
    try:
        modo = t.getTaskMode()
        return modo is not None and "MANUAL" in str(modo)
    except Exception:
        return False


def _tipo_restricao(t) -> int:
    try:
        tipo = t.getConstraintType()
        return _TIPO_RESTRICAO.get(str(tipo), 0)
    except Exception:
        return 0


def _folga_horas(t):
    try:
        return _duracao_para_horas(t.getTotalSlack())
    except Exception:
        return None


def _wbs(t) -> str:
    try:
        return str(t.getWBS() or "")
    except Exception:
        return ""


def _contar_baselines_salvas(t) -> int:
    """Conta quantos números de linha de base (0 a 10) têm data de início ou
    término salva na tarefa (normalmente a tarefa-resumo do projeto)."""
    total = 0
    try:
        if t.getBaselineStart() is not None or t.getBaselineFinish() is not None:
            total += 1
    except Exception:
        pass
    for n in range(1, 11):
        try:
            if t.getBaselineStart(n) is not None or t.getBaselineFinish(n) is not None:
                total += 1
        except Exception:
            continue
    return total


def ler_mpp(caminho: str) -> Projeto:
    """Lê um arquivo .mpp (ou qualquer formato suportado pelo MPXJ) via a biblioteca mpxj.

    Requer Java instalado na máquina e o pacote Python 'mpxj' (pip install mpxj).
    """
    try:
        import jpype

        if not jpype.isJVMStarted():
            jpype.startJVM()
        from org.mpxj.reader import UniversalProjectReader
    except Exception as exc:
        raise MpxjIndisponivelError(
            "Não foi possível carregar o suporte a arquivos .mpp. "
            "Isso exige o Java instalado e o pacote 'mpxj' (pip install mpxj). "
            "Como alternativa, exporte o cronograma do MS Project como XML "
            "(Arquivo > Salvar Como > tipo 'XML') e envie esse arquivo."
        ) from exc

    projeto_mpxj = UniversalProjectReader().read(caminho)
    if projeto_mpxj is None:
        raise MpxjIndisponivelError("O arquivo não pôde ser interpretado como um cronograma de projeto.")

    propriedades = projeto_mpxj.getProjectProperties()

    tarefas: list[Tarefa] = []
    recursos_por_uid: dict[str, Recurso] = {}

    for r in projeto_mpxj.getResources():
        uid = str(r.getUniqueID())
        recursos_por_uid[uid] = Recurso(
            uid=uid,
            nome=str(r.getName() or f"Recurso {uid}"),
            trabalho_horas=_duracao_para_horas(r.getWork()),
            custo=_num(r.getCost()),
        )

    numero_baselines_salvas = 0
    for t in projeto_mpxj.getTasks():
        if t.getUniqueID() == 0 and t.getName() is None:
            continue
        uid = str(t.getUniqueID())
        if int(t.getOutlineLevel() or 0) == 0:
            numero_baselines_salvas = _contar_baselines_salvas(t)
        tarefa = Tarefa(
            uid=uid,
            id=int(t.getID() or 0),
            nome=str(t.getName() or "(sem nome)"),
            nivel_esquema=int(t.getOutlineLevel() or 0),
            resumo=bool(t.getSummary()),
            marco=bool(t.getMilestone()),
            critica=bool(t.getCritical()),
            percentual_concluido=_num(t.getPercentageComplete()),
            inicio=_para_data(t.getStart()),
            termino=_para_data(t.getFinish()),
            inicio_linha_base=_para_data(t.getBaselineStart()),
            termino_linha_base=_para_data(t.getBaselineFinish()),
            inicio_real=_para_data(t.getActualStart()),
            termino_real=_para_data(t.getActualFinish()),
            duracao_horas=_duracao_para_horas(t.getDuration()),
            duracao_linha_base_horas=_duracao_para_horas(t.getBaselineDuration()),
            duracao_real_horas=_duracao_para_horas(t.getActualDuration()),
            custo=_num(t.getCost()),
            custo_linha_base=_num(t.getBaselineCost()),
            custo_real=_num(t.getActualCost()),
            manual=_manual(t),
            tipo_restricao=_tipo_restricao(t),
            folga_horas=_folga_horas(t),
            wbs=_wbs(t),
        )
        for relacao in t.getPredecessors() or []:
            tarefa_pred = relacao.getTargetTask()
            if tarefa_pred is None:
                continue
            tipo = _TIPO_RELACAO.get(str(relacao.getType()), 1)
            tarefa.dependencias.append(
                Dependencia(predecessora_uid=str(tarefa_pred.getUniqueID()), tipo=tipo)
            )
        tarefas.append(tarefa)

    for a in projeto_mpxj.getResourceAssignments():
        tarefa_mpxj = a.getTask()
        recurso_mpxj = a.getResource()
        if tarefa_mpxj is None or recurso_mpxj is None:
            continue
        recurso = recursos_por_uid.get(str(recurso_mpxj.getUniqueID()))
        if recurso is None:
            continue
        uid_tarefa = str(tarefa_mpxj.getUniqueID())
        for tarefa in tarefas:
            if tarefa.uid == uid_tarefa:
                tarefa.recursos.append(recurso.nome)
                break

    if not tarefas:
        raise MpxjIndisponivelError("O arquivo não contém tarefas.")

    return Projeto(
        nome=str(propriedades.getName() or propriedades.getProjectTitle() or "Projeto sem nome"),
        inicio=_para_data(propriedades.getStartDate()),
        termino=_para_data(propriedades.getFinishDate()),
        data_status=_para_data(propriedades.getStatusDate()),
        numero_baselines_salvas=numero_baselines_salvas,
        tarefas=tarefas,
        recursos=list(recursos_por_uid.values()),
    )
