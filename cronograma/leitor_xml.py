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


def _campos_peso_candidatos(raiz, ns) -> list[tuple[str, str]]:
    """Procura, entre os campos personalizados do projeto (<ExtendedAttributes>), todos
    cujo apelido (Alias) contenha 'peso' ou 'weight'. Retorna a lista de (field_id, alias)
    na ordem em que aparecem no arquivo (pode ser vazia se não houver nenhum)."""
    el_atributos = raiz.find(f"{ns}ExtendedAttributes")
    if el_atributos is None:
        return []
    candidatos = []
    for el in el_atributos.findall(f"{ns}ExtendedAttribute"):
        alias = _texto(el, "Alias", ns)
        field_id = _texto(el, "FieldID", ns)
        if alias and field_id and ("peso" in alias.lower() or "weight" in alias.lower()):
            candidatos.append((field_id, alias))
    return candidatos


def _melhor_campo_peso(
    candidatos: list[tuple[str, str]], tem_valor_por_campo: dict[str, bool]
) -> tuple[str, str] | None:
    """Entre os campos candidatos, escolhe o mais provável de ser o peso 'puro' da
    tarefa (e não, por exemplo, um campo calculado que soma peso x avanço): primeiro um
    apelido igual a 'peso'/'weight', depois um que comece com esses termos, e por fim a
    ordem em que aparecem no arquivo. Ignora campos sem nenhum valor preenchido em
    nenhuma tarefa (campos calculados por fórmula podem não ter valor exportado)."""

    def prioridade(candidato: tuple[str, str]) -> int:
        alias_normalizado = candidato[1].strip().lower()
        if alias_normalizado in ("peso", "weight"):
            return 0
        if alias_normalizado.startswith("peso") or alias_normalizado.startswith("weight"):
            return 1
        return 2

    for field_id, alias in sorted(candidatos, key=prioridade):
        if tem_valor_por_campo.get(field_id):
            return field_id, alias
    return None


def _valor_peso_personalizado(elemento_tarefa, ns, field_id: str) -> float | None:
    """Lê, na tarefa, o valor do campo personalizado de peso identificado por field_id."""
    for el in elemento_tarefa.findall(f"{ns}ExtendedAttribute"):
        if _texto(el, "FieldID", ns) == field_id:
            valor_texto = _texto(el, "Value", ns)
            if not valor_texto:
                return None
            valor_texto = valor_texto.strip().replace("%", "").replace(",", ".")
            try:
                return float(valor_texto)
            except ValueError:
                return None
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
    # A maioria das exportações em XML não inclui a data em que a linha de base foi
    # salva (isso normalmente só existe no .mpp nativo); tenta mesmo assim, caso
    # alguma versão do MS Project inclua esse campo.
    data_salva_linha_base = _data(_texto(raiz, "BaselineDate", ns))
    campos_peso_candidatos = _campos_peso_candidatos(raiz, ns)

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
    valores_peso_candidatos: list[dict[str, float | None]] = []
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
        valores_peso_candidatos.append(
            {
                field_id: _valor_peso_personalizado(el, ns, field_id)
                for field_id, _ in campos_peso_candidatos
            }
        )

    if numero_baselines_salvas == 0 and numero_baselines_primeira_tarefa:
        # Nem toda exportação inclui uma tarefa-resumo de nível 0; nesse caso, usa a
        # primeira tarefa do arquivo como referência para contar as linhas de base.
        numero_baselines_salvas = numero_baselines_primeira_tarefa

    tem_valor_por_campo = {
        field_id: any(v.get(field_id) is not None for v in valores_peso_candidatos)
        for field_id, _ in campos_peso_candidatos
    }
    campo_peso_escolhido = _melhor_campo_peso(campos_peso_candidatos, tem_valor_por_campo)
    if campo_peso_escolhido is not None:
        for tarefa, valores_candidatos in zip(tarefas, valores_peso_candidatos):
            tarefa.peso_editado = valores_candidatos.get(campo_peso_escolhido[0])

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
        data_salva_linha_base=data_salva_linha_base,
        nome_coluna_peso_editado=campo_peso_escolhido[1] if campo_peso_escolhido else None,
        tarefas=tarefas,
        recursos=list(recursos_por_uid.values()),
    )
