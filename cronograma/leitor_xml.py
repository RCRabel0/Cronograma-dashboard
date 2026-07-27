import re
import xml.etree.ElementTree as ET
from datetime import datetime, date

from .modelos import Dependencia, Projeto, Recurso, Tarefa

_RE_DURACAO = re.compile(
    r"P(?:(?P<dias>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<horas>\d+(?:\.\d+)?)H)?(?:(?P<minutos>\d+(?:\.\d+)?)M)?(?:(?P<segundos>\d+(?:\.\d+)?)S)?)?"
)


class ArquivoInvalidoError(Exception):
    pass


def _duracao_para_horas(texto: str | None) -> float:
    if not texto:
        return 0.0
    m = _RE_DURACAO.match(texto.strip())
    if not m:
        return 0.0
    partes = m.groupdict()
    dias = float(partes["dias"] or 0)
    horas = float(partes["horas"] or 0)
    minutos = float(partes["minutos"] or 0)
    segundos = float(partes["segundos"] or 0)
    return dias * 24 + horas + minutos / 60 + segundos / 3600


def _data(texto: str | None) -> date | None:
    if not texto:
        return None
    texto = texto.strip()
    if not texto:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto[:19], fmt).date()
        except ValueError:
            continue
    return None


def _texto(elemento, tag, ns) -> str | None:
    filho = elemento.find(f"{ns}{tag}")
    return filho.text if filho is not None else None


def _float(texto: str | None, divisor: float = 1.0) -> float:
    if not texto:
        return 0.0
    try:
        return float(texto) / divisor
    except ValueError:
        return 0.0


def _baseline_zero(elemento, ns):
    """Retorna o elemento <Baseline> com <Number>0</Number>, se existir.

    Além dos campos planos BaselineStart/BaselineFinish/BaselineDuration/BaselineCost
    (usados em exportações mais antigas), o MS Project também pode exportar a linha de
    base como um elemento <Baseline><Number>0</Number>...</Baseline> dentro de cada tarefa.
    """
    for baseline in elemento.findall(f"{ns}Baseline"):
        if _texto(baseline, "Number", ns) == "0":
            return baseline
    return None


def _campo_linha_base(elemento, baseline0, ns, campo: str) -> str | None:
    valor = _texto(elemento, f"Baseline{campo}", ns)
    if valor:
        return valor
    if baseline0 is not None:
        return _texto(baseline0, campo, ns)
    return None


def _contar_baselines_salvas(elemento_tarefa, ns) -> int:
    """Conta quantos números de linha de base (0 a 10) têm de fato uma data de
    início ou término salva na tarefa (normalmente a tarefa-resumo do projeto)."""
    total = 0
    for baseline in elemento_tarefa.findall(f"{ns}Baseline"):
        if _texto(baseline, "Start", ns) or _texto(baseline, "Finish", ns):
            total += 1
    if total == 0 and (_texto(elemento_tarefa, "BaselineStart", ns) or _texto(elemento_tarefa, "BaselineFinish", ns)):
        total = 1
    return total


def ler_xml(caminho: str) -> Projeto:
    """Lê um arquivo MSPDI (XML exportado do MS Project) e retorna um Projeto."""
    try:
        arvore = ET.parse(caminho)
    except ET.ParseError as exc:
        raise ArquivoInvalidoError(
            "O arquivo não é um XML válido. Verifique se foi exportado corretamente do MS Project."
        ) from exc

    raiz = arvore.getroot()
    ns = ""
    if raiz.tag.startswith("{"):
        uri = raiz.tag.split("}")[0] + "}"
        ns = uri

    if not raiz.tag.endswith("Project"):
        raise ArquivoInvalidoError(
            "O arquivo XML não parece ser um cronograma do MS Project (elemento raiz <Project> não encontrado)."
        )

    nome_projeto = _texto(raiz, "Name", ns) or _texto(raiz, "Title", ns) or "Projeto sem nome"
    inicio_projeto = _data(_texto(raiz, "StartDate", ns))
    termino_projeto = _data(_texto(raiz, "FinishDate", ns))
    data_status = _data(_texto(raiz, "StatusDate", ns)) or _data(_texto(raiz, "CurrentDate", ns))

    recursos_por_uid: dict[str, Recurso] = {}
    el_recursos = raiz.find(f"{ns}Resources")
    if el_recursos is not None:
        for el in el_recursos.findall(f"{ns}Resource"):
            uid = _texto(el, "UID", ns) or ""
            nome = _texto(el, "Name", ns) or f"Recurso {uid}"
            recursos_por_uid[uid] = Recurso(
                uid=uid,
                nome=nome,
                trabalho_horas=_duracao_para_horas(_texto(el, "Work", ns)),
                custo=_float(_texto(el, "Cost", ns)),
            )

    tarefas: list[Tarefa] = []
    tarefas_por_uid: dict[str, Tarefa] = {}
    el_tarefas = raiz.find(f"{ns}Tasks")
    if el_tarefas is None:
        raise ArquivoInvalidoError("Nenhuma tarefa encontrada no arquivo (<Tasks> ausente).")

    numero_baselines_salvas = 0
    numero_baselines_primeira_tarefa = None
    for el in el_tarefas.findall(f"{ns}Task"):
        uid = _texto(el, "UID", ns) or ""
        nome = _texto(el, "Name", ns) or "(sem nome)"
        baseline0 = _baseline_zero(el, ns)
        if numero_baselines_primeira_tarefa is None:
            numero_baselines_primeira_tarefa = _contar_baselines_salvas(el, ns)
        if _texto(el, "OutlineLevel", ns) == "0":
            numero_baselines_salvas = _contar_baselines_salvas(el, ns)

        tarefa = Tarefa(
            uid=uid,
            id=int(_texto(el, "ID", ns) or 0),
            nome=nome,
            nivel_esquema=int(_texto(el, "OutlineLevel", ns) or 0),
            resumo=(_texto(el, "Summary", ns) == "1"),
            marco=(_texto(el, "Milestone", ns) == "1"),
            critica=(_texto(el, "Critical", ns) == "1"),
            percentual_concluido=_float(_texto(el, "PercentComplete", ns)),
            inicio=_data(_texto(el, "Start", ns)),
            termino=_data(_texto(el, "Finish", ns)),
            inicio_linha_base=_data(_campo_linha_base(el, baseline0, ns, "Start")),
            termino_linha_base=_data(_campo_linha_base(el, baseline0, ns, "Finish")),
            inicio_real=_data(_texto(el, "ActualStart", ns)),
            termino_real=_data(_texto(el, "ActualFinish", ns)),
            duracao_horas=_duracao_para_horas(_texto(el, "Duration", ns)),
            duracao_linha_base_horas=_duracao_para_horas(_campo_linha_base(el, baseline0, ns, "Duration")),
            duracao_real_horas=_duracao_para_horas(_texto(el, "ActualDuration", ns)),
            custo=_float(_texto(el, "Cost", ns)),
            custo_linha_base=_float(_campo_linha_base(el, baseline0, ns, "Cost")),
            custo_real=_float(_texto(el, "ActualCost", ns)),
            manual=(_texto(el, "Manual", ns) == "1"),
            tipo_restricao=int(_texto(el, "ConstraintType", ns) or 0),
            folga_horas=(
                _float(_texto(el, "TotalSlack", ns)) / 60
                if _texto(el, "TotalSlack", ns) is not None
                else None
            ),
            wbs=_texto(el, "WBS", ns) or "",
        )
        for el_pred in el.findall(f"{ns}PredecessorLink"):
            pred_uid = _texto(el_pred, "PredecessorUID", ns)
            if pred_uid:
                tipo = int(_texto(el_pred, "Type", ns) or 1)
                tarefa.dependencias.append(Dependencia(predecessora_uid=pred_uid, tipo=tipo))
        tarefas.append(tarefa)
        tarefas_por_uid[uid] = tarefa

    if numero_baselines_salvas == 0 and numero_baselines_primeira_tarefa:
        # Nem toda exportação inclui uma tarefa-resumo de nível 0; nesse caso, usa a
        # primeira tarefa do arquivo como referência para contar as linhas de base.
        numero_baselines_salvas = numero_baselines_primeira_tarefa

    el_atribuicoes = raiz.find(f"{ns}Assignments")
    if el_atribuicoes is not None:
        for el in el_atribuicoes.findall(f"{ns}Assignment"):
            task_uid = _texto(el, "TaskUID", ns)
            res_uid = _texto(el, "ResourceUID", ns)
            tarefa = tarefas_por_uid.get(task_uid or "")
            recurso = recursos_por_uid.get(res_uid or "")
            if tarefa is not None and recurso is not None:
                tarefa.recursos.append(recurso.nome)

    if not tarefas:
        raise ArquivoInvalidoError("O arquivo não contém tarefas.")

    return Projeto(
        nome=nome_projeto,
        inicio=inicio_projeto,
        termino=termino_projeto,
        data_status=data_status,
        numero_baselines_salvas=numero_baselines_salvas,
        tarefas=tarefas,
        recursos=list(recursos_por_uid.values()),
    )
