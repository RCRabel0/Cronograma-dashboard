from dataclasses import dataclass, field
from datetime import date

from .i18n import t, tf
from .metricas import Indicadores
from .modelos import Projeto, Tarefa

PONTOS = {"Conforme": 2, "Parcial": 1, "Não Conforme": 0}

OPCOES_MANUAL = ["Não avaliado", "Conforme", "Parcial", "Não Conforme"]

FAIXAS_MATURIDADE = [
    (95, 100.0001, "Excelente"),
    (85, 95, "Muito bom"),
    (70, 85, "Adequado, com melhorias"),
    (50, 70, "Baixa maturidade"),
    (0, 50, "Cronograma inadequado para controle"),
]


@dataclass
class ItemChecklist:
    secao: str
    texto: str
    tipo: str  # "auto" ou "manual"
    chave: str
    status: str | None = None  # preenchido para itens "auto"; None para "manual" (aguarda resposta do usuário)
    evidencia: str = ""


def classificar_maturidade(pct: float) -> str:
    for minimo, maximo, nome in FAIXAS_MATURIDADE:
        if minimo <= pct < maximo or (maximo == 100.0001 and pct == 100):
            return nome
    return "N/D"


def _classificar_taxa(qtd_problema: int, total: int, limite_parcial_pct: float = 5, limite_nc_pct: float = 15) -> str:
    if total == 0:
        return "N/A"
    pct = qtd_problema / total * 100
    if pct == 0:
        return "Conforme"
    if pct <= limite_parcial_pct:
        return "Parcial"
    return "Não Conforme"


def avaliar_checklist(projeto: Projeto, indicadores: Indicadores, idioma: str = "pt") -> list[ItemChecklist]:
    itens: list[ItemChecklist] = []
    tarefas = projeto.tarefas_detalhe
    total = len(tarefas)
    contador = {"n": 0}

    def prox_chave() -> str:
        contador["n"] += 1
        return f"item_{contador['n']}"

    def auto(secao, texto, status, evidencia=""):
        itens.append(
            ItemChecklist(
                secao=t(secao, idioma), texto=t(texto, idioma), tipo="auto", chave=prox_chave(),
                status=status, evidencia=evidencia,
            )
        )

    def manual(secao, texto):
        itens.append(ItemChecklist(secao=t(secao, idioma), texto=t(texto, idioma), tipo="manual", chave=prox_chave()))

    uids_referenciados = {dep.predecessora_uid for t_ in tarefas for dep in t_.dependencias}

    def tem_predecessora(t: Tarefa) -> bool:
        return len(t.dependencias) > 0

    def tem_sucessora(t: Tarefa) -> bool:
        return t.uid in uids_referenciados

    # 1. Estrutura do Cronograma (WBS)
    s = "1. Estrutura do Cronograma (WBS)"
    manual(s, "Todas as entregas do projeto estão representadas.")
    tem_hierarquia = any(t.nivel_esquema > 1 for t in tarefas)
    auto(
        s, "Existe uma Estrutura Analítica do Projeto (EAP/WBS).",
        "Conforme" if tem_hierarquia else "Não Conforme",
        t("Hierarquia de níveis (OutlineLevel) encontrada no arquivo.", idioma) if tem_hierarquia else t("Nenhuma hierarquia de níveis encontrada.", idioma),
    )
    tem_fases = any(t.resumo for t in projeto.tarefas)
    auto(
        s, "As atividades estão organizadas em fases.",
        "Conforme" if tem_fases else "Não Conforme",
        t("Tarefas-resumo (fases/grupos) encontradas.", idioma) if tem_fases else t("Nenhuma tarefa-resumo encontrada no arquivo.", idioma),
    )
    manual(s, "Existem tarefas-resumo apenas para agrupamento.")
    orfas = [t for t in tarefas if not t.marco and not tem_predecessora(t) and not tem_sucessora(t)]
    auto(
        s, "Não existem atividades órfãs.",
        _classificar_taxa(len(orfas), total),
        tf("{n} de {total} tarefas sem predecessora e sem sucessora.", idioma, n=len(orfas), total=total),
    )
    manual(s, "O nível de detalhamento está adequado.")
    manual(s, "Todas as atividades possuem nome claro utilizando verbo + objeto.")

    # 2. Atividades
    s = "2. Atividades"
    sem_duracao = [t for t in tarefas if not t.marco and t.duracao_horas <= 0]
    auto(s, "Todas as atividades possuem duração.", _classificar_taxa(len(sem_duracao), total), tf("{n} de {total} tarefas (não-marco) sem duração.", idioma, n=len(sem_duracao), total=total))
    negativas = [t for t in tarefas if t.duracao_horas < 0]
    auto(s, "Não existem atividades com duração negativa.", "Conforme" if not negativas else "Não Conforme", tf("{n} tarefa(s) com duração negativa.", idioma, n=len(negativas)))
    longas = [t for t in tarefas if not t.marco and t.duracao_horas / 8 > 20]
    auto(s, "Não existem atividades excessivamente longas (ex.: >20 dias).", _classificar_taxa(len(longas), total), tf("{n} de {total} tarefas com duração acima de 20 dias úteis (assumindo 8h/dia).", idioma, n=len(longas), total=total))
    curtas = [t for t in tarefas if not t.marco and 0 < t.duracao_horas < 1]
    auto(s, "Não existem atividades excessivamente curtas sem necessidade.", _classificar_taxa(len(curtas), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas com menos de 1 hora de duração (avalie se fazem sentido).", idioma, n=len(curtas), total=total))
    manual(s, "Existem marcos apenas quando realmente representam entregas.")
    marcos = [t for t in tarefas if t.marco]
    marcos_com_duracao = [t for t in marcos if t.duracao_horas != 0]
    auto(
        s, "Os marcos possuem duração zero.",
        _classificar_taxa(len(marcos_com_duracao), len(marcos)) if marcos else "N/A",
        tf("{n} de {total_marcos} marcos com duração diferente de zero.", idioma, n=len(marcos_com_duracao), total_marcos=len(marcos)) if marcos else t("Nenhum marco encontrado no arquivo.", idioma),
    )

    # 3. Relacionamentos
    s = "3. Relacionamentos"
    sem_pred = [t for t in tarefas if not tem_predecessora(t)]
    auto(s, "Todas as atividades possuem predecessora.", _classificar_taxa(len(sem_pred), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas sem predecessora (a primeira tarefa do cronograma normalmente não tem).", idioma, n=len(sem_pred), total=total))
    sem_suc = [t for t in tarefas if not tem_sucessora(t)]
    auto(s, "Todas possuem sucessora (exceto a última).", _classificar_taxa(len(sem_suc), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas sem sucessora (a última tarefa do cronograma normalmente não tem).", idioma, n=len(sem_suc), total=total))
    auto(s, "Não existem atividades soltas.", _classificar_taxa(len(orfas), total), tf("{n} de {total} tarefas sem predecessora E sem sucessora ao mesmo tempo.", idioma, n=len(orfas), total=total))
    contagem_tipos = {0: 0, 1: 0, 2: 0, 3: 0}
    for tarefa_dep in tarefas:
        for dep in tarefa_dep.dependencias:
            contagem_tipos[dep.tipo] = contagem_tipos.get(dep.tipo, 0) + 1
    nomes_tipo = {
        0: t("Término-Término (FF)", idioma),
        1: t("Término-Início (FS)", idioma),
        2: t("Início-Término (SF)", idioma),
        3: t("Início-Início (SS)", idioma),
    }
    distribuicao = ", ".join(f"{nomes_tipo[k]}: {v}" for k, v in contagem_tipos.items() if v)
    manual(s, tf("O tipo de relacionamento está correto (FS/SS/FF/SF). Distribuição encontrada: {dist}.", idioma, dist=distribuicao or t("nenhum vínculo encontrado", idioma)))
    manual(s, "Leads e Lags foram utilizados somente quando necessários.")
    manual(s, "Não existem lags excessivos.")
    vinculos_vistos = set()
    redundantes = 0
    for tarefa_dep in tarefas:
        for dep in tarefa_dep.dependencias:
            chave_vinculo = (tarefa_dep.uid, dep.predecessora_uid, dep.tipo)
            if chave_vinculo in vinculos_vistos:
                redundantes += 1
            vinculos_vistos.add(chave_vinculo)
    auto(s, "Não existem relacionamentos redundantes.", "Conforme" if redundantes == 0 else "Não Conforme", tf("{n} vínculo(s) duplicado(s) encontrado(s).", idioma, n=redundantes))

    # 4. Restrições
    s = "4. Restrições"
    nao_asap = [t for t in tarefas if t.tipo_restricao != 0]
    auto(s, "As atividades utilizam ASAP (As Soon As Possible) sempre que possível.", _classificar_taxa(len(nao_asap), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas com restrição diferente de ASAP.", idioma, n=len(nao_asap), total=total))
    rigidas = [t for t in tarefas if t.tipo_restricao in (2, 3)]
    auto(s, "Não existem restrições rígidas desnecessárias (Must Start On / Must Finish On).", _classificar_taxa(len(rigidas), total), tf("{n} de {total} tarefas com restrição rígida (MSO/MFO).", idioma, n=len(rigidas), total=total))
    manuais = [t for t in tarefas if t.manual]
    auto(s, "Datas foram controladas pelo vínculo e não digitadas manualmente.", _classificar_taxa(len(manuais), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas em modo de agendamento manual.", idioma, n=len(manuais), total=total))

    # 5. Calendário
    s = "5. Calendário"
    manual(s, "O calendário do projeto está correto.")
    manual(s, "Calendários de recursos foram definidos quando necessário.")
    manual(s, "Feriados estão cadastrados.")
    manual(s, "Jornadas especiais estão configuradas.")
    manual(s, "Não existem calendários incorretos atribuídos.")

    # 6. Recursos
    s = "6. Recursos"
    sem_responsavel = [t for t in tarefas if not t.marco and not t.recursos]
    auto(s, "Todas as atividades possuem responsável.", _classificar_taxa(len(sem_responsavel), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas (não-marco) sem recurso atribuído.", idioma, n=len(sem_responsavel), total=total))
    manual(s, "Recursos estão corretamente cadastrados.")
    nomes_recursos = [r.nome.strip().lower() for r in projeto.recursos]
    duplicados_recursos = len(nomes_recursos) - len(set(nomes_recursos))
    auto(s, "Não existem recursos duplicados.", "Conforme" if duplicados_recursos == 0 else "Não Conforme", tf("{n} nome(s) de recurso duplicado(s) de {total} recurso(s).", idioma, n=duplicados_recursos, total=len(nomes_recursos)))
    manual(s, "As unidades de alocação estão corretas.")
    manual(s, "Não existem superalocações sem tratamento.")
    manual(s, "Recursos genéricos estão identificados.")

    # 7. Custos (quando utilizados)
    s = "7. Custos (quando utilizados)"
    if projeto.tem_custo:
        sem_custo = [r for r in projeto.recursos if r.custo <= 0]
        auto(s, "Recursos possuem custo.", _classificar_taxa(len(sem_custo), len(projeto.recursos)) if projeto.recursos else "N/A", tf("{n} de {total} recursos sem custo definido.", idioma, n=len(sem_custo), total=len(projeto.recursos)))
    else:
        auto(s, "Recursos possuem custo.", "N/A", "Arquivo não tem custos de recursos preenchidos.")
    manual(s, "Custos fixos foram cadastrados quando necessário.")
    if projeto.tem_custo:
        tem_baseline_custo = any(t.custo_linha_base > 0 for t in tarefas)
        auto(s, "Baseline de custo foi salva.", "Conforme" if tem_baseline_custo else "Não Conforme", t("Custo de linha de base encontrado.", idioma) if tem_baseline_custo else t("Nenhum custo de linha de base encontrado.", idioma))
    else:
        auto(s, "Baseline de custo foi salva.", "N/A", "Arquivo não tem custos de recursos preenchidos.")
    manual(s, "Fluxo financeiro acompanha o cronograma.")

    # 8. Linha de Base (Baseline)
    s = "8. Linha de Base (Baseline)"
    com_baseline = [t for t in tarefas if t.inicio_linha_base is not None]
    auto(s, "Baseline foi salva.", _classificar_taxa(total - len(com_baseline), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas com linha de base identificada.", idioma, n=len(com_baseline), total=total))
    auto(s, "Data inicial da baseline existe.", "Conforme" if any(t.inicio_linha_base for t in tarefas) else "Não Conforme", tf("{n} de {total} tarefas com Início (linha de base).", idioma, n=sum(1 for t in tarefas if t.inicio_linha_base), total=total))
    auto(s, "Data final da baseline existe.", "Conforme" if any(t.termino_linha_base for t in tarefas) else "Não Conforme", tf("{n} de {total} tarefas com Término (linha de base).", idioma, n=sum(1 for t in tarefas if t.termino_linha_base), total=total))
    tem_trabalho_baseline = any(t.duracao_linha_base_horas > 0 for t in tarefas)
    auto(s, "Trabalho (duração) baseline registrado.", "Conforme" if tem_trabalho_baseline else "Não Conforme", t("Duração de linha de base encontrada.", idioma) if tem_trabalho_baseline else t("Nenhuma duração de linha de base encontrada.", idioma))
    if projeto.tem_custo:
        tem_custo_baseline = any(t.custo_linha_base > 0 for t in tarefas)
        auto(s, "Custo baseline registrado.", "Conforme" if tem_custo_baseline else "Não Conforme", t("Custo de linha de base encontrado.", idioma) if tem_custo_baseline else t("Nenhum custo de linha de base encontrado.", idioma))
    else:
        auto(s, "Custo baseline registrado.", "N/A", "Arquivo não tem custos de recursos preenchidos.")

    # 9. Caminho Crítico
    s = "9. Caminho Crítico"
    tem_critico = any(t.critica for t in tarefas)
    auto(s, "Caminho crítico identificado.", "Conforme" if tem_critico else "Não Conforme", tf("{n} de {total} tarefas marcadas como críticas.", idioma, n=sum(1 for t in tarefas if t.critica), total=total))
    manual(s, "O caminho crítico faz sentido.")
    manual(s, "Não existem vários caminhos críticos sem justificativa.")
    com_folga = [t for t in tarefas if t.folga_horas is not None]
    auto(s, "Float Total (folga) foi analisado.", "Conforme" if com_folga else "Não Conforme", tf("Folga total disponível em {n} de {total} tarefas.", idioma, n=len(com_folga), total=total) if com_folga else t("Folga total não encontrada no arquivo.", idioma))
    negativas_folga = [t for t in com_folga if t.folga_horas < 0]
    auto(s, "Folgas negativas foram investigadas.", "Conforme" if not negativas_folga else "Não Conforme", tf("{n} tarefa(s) com folga total negativa.", idioma, n=len(negativas_folga)) if com_folga else t("N/A — folga total não disponível no arquivo.", idioma))

    # 10. Atualização
    s = "10. Atualização"
    auto(s, "Data de Status definida.", "Conforme" if projeto.data_status else "Não Conforme", tf("Data de status: {data}", idioma, data=projeto.data_status) if projeto.data_status else t("Nenhuma data de status encontrada.", idioma))
    tem_progresso = any(t.percentual_concluido > 0 for t in tarefas)
    auto(s, "Progresso atualizado.", "Conforme" if tem_progresso else "Não Conforme", t("Ao menos uma tarefa com % concluído maior que zero.", idioma) if tem_progresso else t("Nenhuma tarefa com progresso registrado.", idioma))
    incoerentes = []
    if projeto.data_status:
        incoerentes = [t for t in tarefas if t.inicio and t.inicio > projeto.data_status and t.percentual_concluido > 0]
    auto(s, "% Completo coerente com a data de status.", _classificar_taxa(len(incoerentes), total) if projeto.data_status else "N/A", tf("{n} de {total} tarefas com início futuro (após a data de status) e progresso maior que zero.", idioma, n=len(incoerentes), total=total))
    manual(s, "Trabalho restante atualizado.")
    concluidas_sem_data_real = [t for t in tarefas if t.percentual_concluido >= 100 and t.termino_real is None]
    concluidas = [t for t in tarefas if t.percentual_concluido >= 100]
    auto(s, "Atividades concluídas possuem data real de término.", _classificar_taxa(len(concluidas_sem_data_real), len(concluidas)) if concluidas else "N/A", tf("{n} de {total_concluidas} tarefas concluídas sem Término Real registrado.", idioma, n=len(concluidas_sem_data_real), total_concluidas=len(concluidas)))
    auto(s, "Atividades futuras não possuem progresso indevido.", _classificar_taxa(len(incoerentes), total) if projeto.data_status else "N/A", tf("{n} de {total} tarefas com início futuro e progresso indevido.", idioma, n=len(incoerentes), total=total))

    # 11. Indicadores
    s = "11. Indicadores"
    auto(s, "SPI calculado.", "Conforme" if indicadores.spi is not None else "Não Conforme", tf("SPI = {spi:.2f}", idioma, spi=indicadores.spi) if indicadores.spi is not None else t("SPI não pôde ser calculado (sem baseline).", idioma))
    auto(s, "CPI calculado (quando aplicável).", "Conforme" if indicadores.cpi is not None else "Não Conforme", tf("CPI = {cpi:.2f}", idioma, cpi=indicadores.cpi) if indicadores.cpi is not None else t("CPI não pôde ser calculado.", idioma))
    auto(s, "Percentual físico atualizado.", "Conforme", tf("% Concluído geral do projeto: {pct:.1f}%.", idioma, pct=indicadores.percentual_concluido))
    if projeto.tem_custo:
        auto(s, "Percentual financeiro atualizado.", "Conforme" if indicadores.ac_total > 0 else "Não Conforme", tf("Custo Real acumulado: {ac:,.2f}.", idioma, ac=indicadores.ac_total))
    else:
        auto(s, "Percentual financeiro atualizado.", "N/A", "Arquivo não tem custos de recursos preenchidos.")
    auto(s, "Curva S disponível.", "Conforme", "Gerada automaticamente na aba Curva S deste programa.")
    manual(s, "Marcos estratégicos monitorados.")
    manual(s, "Aderência ao cronograma monitorada.")

    # 12. Qualidade do Planejamento
    s = "12. Qualidade do Planejamento"
    auto(s, "Não existem tarefas manuais.", _classificar_taxa(len(manuais), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas em modo manual.", idioma, n=len(manuais), total=total))
    auto(s, "Todas as tarefas estão em modo automático.", _classificar_taxa(len(manuais), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas em modo automático.", idioma, n=total - len(manuais), total=total))
    auto(s, "Não existem datas digitadas manualmente (restrições diferentes de ASAP).", _classificar_taxa(len(nao_asap), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas com restrição diferente de ASAP.", idioma, n=len(nao_asap), total=total))
    nomes_tarefas = [t.nome.strip().lower() for t in tarefas]
    duplicadas_tarefas = len(nomes_tarefas) - len(set(nomes_tarefas))
    auto(s, "Não existem atividades duplicadas.", _classificar_taxa(duplicadas_tarefas, total), tf("{n} nome(s) de tarefa duplicado(s) de {total}.", idioma, n=duplicadas_tarefas, total=total))
    auto(s, "Não existem durações muito elevadas.", _classificar_taxa(len(longas), total), tf("{n} de {total} tarefas com duração acima de 20 dias úteis.", idioma, n=len(longas), total=total))
    manual(s, "Dependências fazem sentido lógico.")
    manual(s, "O cronograma pode ser recalculado sem erros (não verificável a partir de um arquivo exportado; confirme no MS Project).")

    # 13. Governança
    s = "13. Governança"
    com_wbs = [t for t in tarefas if t.wbs]
    auto(s, "Código WBS preenchido.", _classificar_taxa(total - len(com_wbs), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas com código WBS preenchido.", idioma, n=len(com_wbs), total=total))
    auto(s, "ID da atividade definido.", "Conforme", "Todas as tarefas possuem ID único atribuído pelo MS Project.")
    auto(s, "Responsável informado.", _classificar_taxa(len(sem_responsavel), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas (não-marco) sem recurso atribuído.", idioma, n=len(sem_responsavel), total=total))
    manual(s, "Disciplina identificada.")
    auto(s, "Fase do projeto definida.", "Conforme" if tem_fases else "Não Conforme", t("Tarefas-resumo (fases) encontradas.", idioma) if tem_fases else t("Nenhuma tarefa-resumo encontrada.", idioma))
    manual(s, "Pacote de trabalho identificado.")
    manual(s, "Marco contratual identificado.")
    manual(s, "Marco executivo identificado.")
    manual(s, "Cliente aprovou a versão.")
    manual(s, "Versão do cronograma registrada.")

    # 14. Campos Personalizados (opcional)
    s = "14. Campos Personalizados (opcional)"
    for campo in [
        "Peso físico.",
        "Criticidade.",
        "Prioridade.",
        "Área responsável.",
        "Status (Verde/Amarelo/Vermelho).",
        "Risco associado.",
        "Percentual planejado.",
        "Percentual realizado.",
        "Data da última atualização.",
    ]:
        manual(s, campo)

    # 15. Auditoria Final
    s = "15. Auditoria Final"
    auto(s, "Não existem atividades sem predecessor.", _classificar_taxa(len(sem_pred), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas sem predecessora.", idioma, n=len(sem_pred), total=total))
    auto(s, "Não existem atividades sem sucessor (exceto a última).", _classificar_taxa(len(sem_suc), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas sem sucessora.", idioma, n=len(sem_suc), total=total))
    auto(s, "Não existem restrições indevidas.", _classificar_taxa(len(rigidas), total), tf("{n} de {total} tarefas com restrição rígida (MSO/MFO).", idioma, n=len(rigidas), total=total))
    manual(s, "Não existem recursos superalocados.")
    auto(s, "Não existem tarefas manuais.", _classificar_taxa(len(manuais), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas em modo manual.", idioma, n=len(manuais), total=total))
    auto(s, "Baseline salva.", _classificar_taxa(total - len(com_baseline), total, limite_parcial_pct=10, limite_nc_pct=25), tf("{n} de {total} tarefas com linha de base identificada.", idioma, n=len(com_baseline), total=total))
    manual(s, "Caminho crítico validado.")
    manual(s, "Calendário correto.")
    auto(s, "Data de Status atualizada.", "Conforme" if projeto.data_status else "Não Conforme", tf("Data de status: {data}", idioma, data=projeto.data_status) if projeto.data_status else t("Nenhuma data de status encontrada.", idioma))
    manual(s, "Cronograma aprovado.")

    return itens


def calcular_pontuacao(itens: list[ItemChecklist], respostas_manuais: dict) -> dict:
    pontos = 0
    maximo = 0
    avaliados = 0
    nao_avaliados = 0
    for item in itens:
        status = item.status if item.tipo == "auto" else respostas_manuais.get(item.chave, "Não avaliado")
        if status in (None, "Não avaliado"):
            nao_avaliados += 1
            continue
        if status == "N/A":
            continue
        pontos += PONTOS.get(status, 0)
        maximo += 2
        avaliados += 1
    percentual = (pontos / maximo * 100) if maximo else 0.0
    return {
        "pontos": pontos,
        "maximo": maximo,
        "percentual": percentual,
        "classificacao": classificar_maturidade(percentual) if maximo else "N/D",
        "itens_avaliados": avaliados,
        "itens_nao_avaliados": nao_avaliados,
        "total_itens": len(itens),
    }
