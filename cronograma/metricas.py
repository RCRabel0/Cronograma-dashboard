import copy
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from .i18n import formatar_data, t, tf
from .modelos import Projeto, Tarefa


@dataclass
class ValoresTarefa:
    tarefa: Tarefa
    pv: float
    ev: float
    ac: float


@dataclass
class Indicadores:
    unidade: str
    pv_total: float
    ev_total: float
    ac_total: float
    spi: float | None
    cpi: float | None
    percentual_concluido: float
    variacao_custo: float
    variacao_custo_pct: float | None
    variacao_prazo: float
    variacao_prazo_pct: float | None
    atraso_dias: int
    custo_previsto_total: float | None
    tarefas_criticas_atrasadas: int
    tarefas_atrasadas: int
    total_tarefas: int
    termino_planejado: date | None = None
    termino_projetado: date | None = None


def formatar_valor(valor: float, unidade: str) -> str:
    if unidade == "R$":
        texto = f"R$ {valor:,.2f}"
    else:
        texto = f"{valor:,.1f} h"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def peso_tarefa(tarefa: Tarefa, metodo_peso: str, tem_custo: bool) -> float:
    """Peso usado como 'valor' da tarefa nos cálculos de EVM.

    'metodo_peso' é 'custo', 'duracao' ou 'peso_editado'. Quando é 'peso_editado' e a
    tarefa tem valor preenchido na coluna personalizada de peso (detectada no MS
    Project), usa esse valor. Caso contrário — ou quando o método pedido é 'custo' mas
    este projeto não tem custos preenchidos — cai para o custo da linha de base (se
    'tem_custo' for True) ou, por fim, para a duração planejada em horas.
    """
    if metodo_peso == "peso_editado" and tarefa.peso_editado is not None:
        return tarefa.peso_editado
    if tem_custo and metodo_peso in ("custo", "peso_editado"):
        return tarefa.custo_linha_base or tarefa.custo
    return tarefa.duracao_linha_base_horas or tarefa.duracao_horas


def valor_realizado_tarefa(tarefa: Tarefa, usa_custo: bool) -> float:
    if usa_custo:
        return tarefa.custo_real
    return tarefa.duracao_real_horas


def _fracao_decorrida(data_status: date, inicio: date | None, termino: date | None) -> float:
    if inicio is None or termino is None or termino <= inicio:
        return 0.0
    if data_status <= inicio:
        return 0.0
    if data_status >= termino:
        return 1.0
    return (data_status - inicio).days / (termino - inicio).days


def calcular_valores_tarefa(
    tarefa: Tarefa, data_status: date, metodo_peso: str, tem_custo: bool
) -> ValoresTarefa:
    fracao_planejada = _fracao_decorrida(data_status, tarefa.inicio_linha_base, tarefa.termino_linha_base)
    peso = peso_tarefa(tarefa, metodo_peso, tem_custo)
    usa_custo = tem_custo and metodo_peso in ("custo", "peso_editado")

    pv = peso * fracao_planejada
    ev = peso * (tarefa.percentual_concluido / 100)

    realizado = valor_realizado_tarefa(tarefa, usa_custo)
    ac = realizado if realizado else peso * (tarefa.percentual_concluido / 100)

    return ValoresTarefa(tarefa=tarefa, pv=pv, ev=ev, ac=ac)


def calcular_indicadores(
    projeto: Projeto, data_status: date | None = None, metodo_peso: str | None = None
) -> Indicadores:
    tarefas = projeto.tarefas_detalhe
    if data_status is None:
        data_status = projeto.data_status or date.today()

    tem_custo = projeto.tem_custo
    if metodo_peso is None:
        metodo_peso = "custo" if tem_custo else "duracao"
    usa_custo = tem_custo and metodo_peso in ("custo", "peso_editado")
    unidade = "R$" if usa_custo else "h"

    valores = [calcular_valores_tarefa(t, data_status, metodo_peso, tem_custo) for t in tarefas]

    pv_total = sum(v.pv for v in valores)
    ev_total = sum(v.ev for v in valores)
    ac_total = sum(v.ac for v in valores)
    orcamento_total = sum(peso_tarefa(t, metodo_peso, tem_custo) for t in tarefas)

    spi = (ev_total / pv_total) if pv_total > 0 else None
    cpi = (ev_total / ac_total) if ac_total > 0 else None

    resumo_projeto = projeto.tarefa_resumo_projeto
    if resumo_projeto is not None:
        percentual_concluido = resumo_projeto.percentual_concluido
    else:
        percentual_concluido = (ev_total / orcamento_total * 100) if orcamento_total > 0 else 0.0

    variacao_custo = ev_total - ac_total
    variacao_custo_pct = (variacao_custo / ev_total * 100) if ev_total > 0 else None

    variacao_prazo = ev_total - pv_total
    variacao_prazo_pct = (variacao_prazo / pv_total * 100) if pv_total > 0 else None

    custo_previsto_total = (orcamento_total / cpi) if cpi else None

    termino_planejado = max(
        (t.termino_linha_base for t in tarefas if t.termino_linha_base is not None), default=None
    )
    termino_projetado = max((t.termino for t in tarefas if t.termino is not None), default=None)
    atraso_dias = 0
    if termino_planejado is not None and termino_projetado is not None:
        atraso_dias = (termino_projetado - termino_planejado).days

    tarefas_atrasadas = [t for t in tarefas if t.atrasada]
    tarefas_criticas_atrasadas = [t for t in tarefas_atrasadas if t.critica]

    return Indicadores(
        unidade=unidade,
        pv_total=pv_total,
        ev_total=ev_total,
        ac_total=ac_total,
        spi=spi,
        cpi=cpi,
        percentual_concluido=percentual_concluido,
        variacao_custo=variacao_custo,
        variacao_custo_pct=variacao_custo_pct,
        variacao_prazo=variacao_prazo,
        variacao_prazo_pct=variacao_prazo_pct,
        atraso_dias=atraso_dias,
        custo_previsto_total=custo_previsto_total,
        tarefas_criticas_atrasadas=len(tarefas_criticas_atrasadas),
        tarefas_atrasadas=len(tarefas_atrasadas),
        total_tarefas=len(tarefas),
        termino_planejado=termino_planejado,
        termino_projetado=termino_projetado,
    )


def dias_atraso_tarefa(tarefa: Tarefa) -> int:
    if tarefa.termino is None or tarefa.termino_linha_base is None:
        return 0
    return (tarefa.termino - tarefa.termino_linha_base).days


def tarefas_maior_mudanca(projeto: Projeto, top_n: int = 5) -> list[dict]:
    """Retorna as tarefas cujo Início/Término mais mudaram em relação à linha de base.

    Ordenado pelo maior desvio absoluto (em dias) entre Término e Término da linha de base.
    """
    candidatos = []
    for t in projeto.tarefas_detalhe:
        if t.termino is None or t.termino_linha_base is None:
            continue
        variacao_termino = (t.termino - t.termino_linha_base).days
        variacao_inicio = (
            (t.inicio - t.inicio_linha_base).days if (t.inicio and t.inicio_linha_base) else None
        )
        if variacao_termino == 0 and (variacao_inicio or 0) == 0:
            continue
        candidatos.append(
            {
                "tarefa": t,
                "variacao_termino": variacao_termino,
                "variacao_inicio": variacao_inicio,
            }
        )
    candidatos.sort(key=lambda c: abs(c["variacao_termino"]), reverse=True)
    return candidatos[:top_n]


def gerar_percepcoes(projeto: Projeto, indicadores: Indicadores, top_n_mudancas: int = 5, idioma: str = "pt") -> list[tuple[str, str]]:
    """Retorna uma lista de (categoria, texto). categoria é um marcador fixo e
    independente de idioma ('alerta', 'sucesso' ou 'info') usado pela interface
    para decidir se mostra st.warning/st.success/st.info."""
    percepcoes: list[tuple[str, str]] = []
    rotulo_cpi = t("CPI (índice de custo)", idioma) if indicadores.unidade == "R$" else t("CPI (índice de eficiência de prazo trabalhado)", idioma)

    if indicadores.spi is None:
        percepcoes.append(
            ("info", t("Não foi possível calcular o SPI (índice de prazo) porque o arquivo não contém dados de linha de base (baseline).", idioma))
        )
    elif indicadores.spi < 0.95:
        percepcoes.append(
            ("alerta", tf(
                "O projeto está atrasado em relação ao planejado (SPI = {spi:.2f}). "
                "O progresso real está abaixo do progresso previsto para a data de status.",
                idioma, spi=indicadores.spi,
            ))
        )
    elif indicadores.spi > 1.05:
        percepcoes.append(("sucesso", tf("O projeto está adiantado em relação ao planejado (SPI = {spi:.2f}).", idioma, spi=indicadores.spi)))
    else:
        percepcoes.append(("sucesso", tf("O projeto está dentro do prazo planejado (SPI = {spi:.2f}).", idioma, spi=indicadores.spi)))

    if indicadores.pv_total > 0:
        sv_formatado = formatar_valor(indicadores.variacao_prazo, indicadores.unidade)
        if indicadores.variacao_prazo < 0:
            percepcoes.append(
                ("alerta", tf(
                    "SV (variância de prazo) = {sv}. Valor negativo indica que o valor agregado (EV) "
                    "está abaixo do planejado (PV) até a data de status — o projeto está atrasado.",
                    idioma, sv=sv_formatado,
                ))
            )
        elif indicadores.variacao_prazo > 0:
            percepcoes.append(
                ("sucesso", tf(
                    "SV (variância de prazo) = {sv}. Valor positivo indica que o valor agregado (EV) "
                    "está acima do planejado (PV) até a data de status — o projeto está adiantado.",
                    idioma, sv=sv_formatado,
                ))
            )
        else:
            percepcoes.append(("sucesso", t("SV (variância de prazo) = 0. O projeto está exatamente em dia com o planejado.", idioma)))

    if indicadores.cpi is None:
        motivo = t("não há custos reais (ActualCost) registrados", idioma) if indicadores.unidade == "R$" else t("não há duração real (ActualDuration) registrada", idioma)
        percepcoes.append(("info", tf("Não foi possível calcular o {rotulo} porque {motivo}.", idioma, rotulo=rotulo_cpi, motivo=motivo)))
    elif indicadores.cpi < 0.95:
        if indicadores.unidade == "R$":
            percepcoes.append(
                ("alerta", tf(
                    "O custo real está acima do orçado ({rotulo} = {cpi:.2f}). "
                    "Se essa tendência continuar, o projeto deve estourar o orçamento.",
                    idioma, rotulo=rotulo_cpi, cpi=indicadores.cpi,
                ))
            )
        else:
            percepcoes.append(("alerta", tf("As tarefas estão consumindo mais tempo do que o planejado ({rotulo} = {cpi:.2f}).", idioma, rotulo=rotulo_cpi, cpi=indicadores.cpi)))
    elif indicadores.cpi > 1.05:
        if indicadores.unidade == "R$":
            percepcoes.append(("sucesso", tf("O projeto está custando menos do que o orçado até o momento ({rotulo} = {cpi:.2f}).", idioma, rotulo=rotulo_cpi, cpi=indicadores.cpi)))
        else:
            percepcoes.append(("sucesso", tf("As tarefas estão sendo concluídas com menos tempo do que o planejado ({rotulo} = {cpi:.2f}).", idioma, rotulo=rotulo_cpi, cpi=indicadores.cpi)))
    else:
        if indicadores.unidade == "R$":
            percepcoes.append(("sucesso", tf("O custo real está alinhado com o orçamento planejado ({rotulo} = {cpi:.2f}).", idioma, rotulo=rotulo_cpi, cpi=indicadores.cpi)))
        else:
            percepcoes.append(("sucesso", tf("O tempo realizado está alinhado com o planejado ({rotulo} = {cpi:.2f}).", idioma, rotulo=rotulo_cpi, cpi=indicadores.cpi)))

    if indicadores.atraso_dias > 0:
        percepcoes.append(("alerta", tf("A data de término projetada está {n} dia(s) além da data de término da linha de base.", idioma, n=indicadores.atraso_dias)))
    elif indicadores.atraso_dias < 0:
        percepcoes.append(("sucesso", tf("A data de término projetada está {n} dia(s) antes da linha de base.", idioma, n=abs(indicadores.atraso_dias))))

    if indicadores.tarefas_criticas_atrasadas > 0:
        percepcoes.append(
            ("alerta", tf(
                "Existem {n} tarefa(s) crítica(s) atrasada(s), "
                "o que representa risco direto para a data final do projeto.",
                idioma, n=indicadores.tarefas_criticas_atrasadas,
            ))
        )

    if indicadores.tarefas_atrasadas > 0:
        percepcoes.append(
            ("alerta", tf(
                "No total, {n} de {total} tarefas "
                "estão atrasadas em relação à linha de base.",
                idioma, n=indicadores.tarefas_atrasadas, total=indicadores.total_tarefas,
            ))
        )
    else:
        percepcoes.append(("sucesso", t("Nenhuma tarefa está atrasada em relação à linha de base.", idioma)))

    percepcoes.append(("info", tf("Progresso geral do projeto: {pct:.1f}% concluído.", idioma, pct=indicadores.percentual_concluido)))

    mudancas = tarefas_maior_mudanca(projeto, top_n=top_n_mudancas)
    if mudancas:
        for c in mudancas:
            tarefa_mudada = c["tarefa"]
            dias = c["variacao_termino"]
            direcao = t("atraso", idioma) if dias > 0 else t("adiantamento", idioma)
            categoria_mudanca = "alerta" if dias > 0 else "info"
            percepcoes.append(
                (categoria_mudanca, tf(
                    "Mudança de planejamento em '{nome}': término foi de "
                    "{data_base} (linha de base) para {data_atual} (atual) "
                    "— {direcao} de {n} dia(s).",
                    idioma,
                    nome=tarefa_mudada.nome,
                    data_base=formatar_data(tarefa_mudada.termino_linha_base, idioma),
                    data_atual=formatar_data(tarefa_mudada.termino, idioma),
                    direcao=direcao,
                    n=abs(dias),
                ))
            )

    return percepcoes


def gerar_recomendacoes(projeto: Projeto, indicadores: Indicadores, top_n: int = 3, idioma: str = "pt") -> list[str]:
    """Sugestões de ação concretas (o que fazer), complementando 'gerar_percepcoes' —
    que só diagnostica o estado do projeto. Cada item já é uma recomendação, não apenas
    uma observação. Baseado nas mesmas regras (SPI/CPI/criticidade) já usadas nas
    percepções, mas formulado como ação."""
    recomendacoes: list[str] = []

    criticas_atrasadas = sorted(
        [t for t in projeto.tarefas_detalhe if t.critica and t.atrasada],
        key=dias_atraso_tarefa, reverse=True,
    )
    for tarefa in criticas_atrasadas[:top_n]:
        recomendacoes.append(tf(
            "Priorize a tarefa crítica '{nome}': está {dias} dia(s) atrasada e impacta "
            "diretamente a data final do projeto. Avalie reforçar recursos ou remover "
            "impedimentos ainda esta semana.",
            idioma, nome=tarefa.nome, dias=dias_atraso_tarefa(tarefa),
        ))

    if indicadores.cpi is not None and indicadores.cpi < 0.9:
        eac_texto = (
            formatar_valor(indicadores.custo_previsto_total, indicadores.unidade)
            if indicadores.custo_previsto_total else t("N/D", idioma)
        )
        if indicadores.unidade == "R$":
            recomendacoes.append(tf(
                "O custo real está significativamente acima do orçado (CPI = {cpi:.2f}). "
                "Revise o escopo ou renegocie o orçamento antes que o estouro projetado "
                "({eac}) se confirme.",
                idioma, cpi=indicadores.cpi, eac=eac_texto,
            ))
        else:
            recomendacoes.append(tf(
                "As tarefas estão consumindo bem mais tempo do que o planejado "
                "(CPI = {cpi:.2f}). Revise as estimativas de duração das próximas atividades.",
                idioma, cpi=indicadores.cpi,
            ))

    if indicadores.spi is not None and indicadores.spi < 0.85:
        recomendacoes.append(tf(
            "O ritmo de execução está bem abaixo do planejado (SPI = {spi:.2f}). Considere "
            "replanejar as próximas atividades com uma linha de base realista, em vez de "
            "manter uma meta que já não é mais alcançável.",
            idioma, spi=indicadores.spi,
        ))

    if indicadores.tarefas_atrasadas > 0 and indicadores.tarefas_criticas_atrasadas == 0:
        recomendacoes.append(t(
            "Há tarefas atrasadas, mas nenhuma delas é crítica no momento — ainda dá para "
            "recuperar o atraso sem afetar a data final, priorizando essas atividades antes "
            "que se tornem críticas.",
            idioma,
        ))

    if not recomendacoes:
        recomendacoes.append(t(
            "Nenhuma ação urgente identificada — continue monitorando os indicadores normalmente.",
            idioma,
        ))

    return recomendacoes[:top_n] if len(recomendacoes) > top_n else recomendacoes


@dataclass
class FaixaPrevisaoTermino:
    otimista: date | None
    realista: date | None
    pessimista: date | None


def calcular_faixa_previsao_termino(indicadores: Indicadores, data_status: date) -> FaixaPrevisaoTermino:
    """Estima uma faixa de término em vez de uma única data, para apoiar decisões de
    quando escalar um problema:

    - Otimista: a data da linha de base original — o cenário 'se nada tivesse saído do
      combinado', usado como referência.
    - Realista: a data projetada pelo cronograma atual, que já reflete atrasos e
      replanejamentos conhecidos.
    - Pessimista: se o trabalho restante continuar no mesmo ritmo de desempenho atual
      (SPI) do que já foi observado, em vez de melhorar — técnica de projeção por SPI
      (Earned Schedule), aplicada só sobre os dias que ainda faltam.
    """
    if indicadores.termino_planejado is None or indicadores.termino_projetado is None:
        return FaixaPrevisaoTermino(otimista=None, realista=None, pessimista=None)

    otimista = indicadores.termino_planejado
    realista = indicadores.termino_projetado

    dias_restantes = (realista - data_status).days
    if indicadores.spi and indicadores.spi > 0 and indicadores.spi < 1 and dias_restantes > 0:
        dias_extra = dias_restantes * (1 / indicadores.spi - 1)
        pessimista = realista + timedelta(days=round(dias_extra))
    else:
        pessimista = realista

    return FaixaPrevisaoTermino(otimista=otimista, realista=realista, pessimista=pessimista)


def avaliar_riscos_tarefas(projeto: Projeto) -> list[dict]:
    """Monta uma matriz de priorização (probabilidade x impacto) a partir das tarefas
    atrasadas. É uma heurística simples baseada em criticidade e magnitude do atraso —
    não substitui uma análise de riscos formal, mas ajuda a priorizar o que merece
    atenção da liderança primeiro. Impacto e probabilidade vão de 1 (baixo) a 3 (alto)."""
    riscos = []
    for tarefa in projeto.tarefas_detalhe:
        if not tarefa.atrasada:
            continue
        dias = dias_atraso_tarefa(tarefa)
        impacto = 3 if tarefa.critica else (2 if dias >= 5 else 1)
        probabilidade = 3 if dias >= 10 else (2 if dias >= 3 else 1)
        riscos.append({
            "tarefa": tarefa.nome,
            "critica": tarefa.critica,
            "atraso_dias": dias,
            "impacto": impacto,
            "probabilidade": probabilidade,
        })
    riscos.sort(key=lambda r: r["impacto"] * r["probabilidade"], reverse=True)
    return riscos


def simular_alteracao_tarefa(
    projeto: Projeto,
    tarefa_uid: str,
    novo_percentual: float | None = None,
    ajuste_dias_termino: int = 0,
) -> Projeto:
    """Retorna uma CÓPIA do projeto com uma tarefa alterada hipoteticamente (% concluído
    e/ou deslocamento do término), para simular 'e se' sem alterar os dados originais.

    Limitação conhecida: não recalcula dependências entre tarefas (não há motor de
    CPM neste programa) — reflete só o efeito direto da tarefa alterada nos indicadores
    agregados e na data de término do projeto (quando ela for a mais tardia)."""
    projeto_simulado = copy.deepcopy(projeto)
    for tarefa in projeto_simulado.tarefas:
        if tarefa.uid == tarefa_uid:
            if novo_percentual is not None:
                tarefa.percentual_concluido = novo_percentual
            if ajuste_dias_termino and tarefa.termino is not None:
                tarefa.termino = tarefa.termino + timedelta(days=ajuste_dias_termino)
            break
    return projeto_simulado


def simular_conclusao_tarefas(projeto: Projeto, uids_tarefas: list[str]) -> Projeto:
    """Retorna uma CÓPIA do projeto com as tarefas informadas marcadas como 100%
    concluídas, para simular 'e se eu terminasse essas tarefas' sem alterar os dados
    originais. Mesma limitação de 'simular_alteracao_tarefa': não recalcula dependências
    entre tarefas nem atualiza datas de término — reflete só o efeito das tarefas
    marcadas nos indicadores agregados de progresso e custo."""
    projeto_simulado = copy.deepcopy(projeto)
    uids_selecionados = set(uids_tarefas)
    for tarefa in projeto_simulado.tarefas:
        if tarefa.uid in uids_selecionados:
            tarefa.percentual_concluido = 100.0
    return projeto_simulado


def identificar_sucessoras_diretas(projeto: Projeto, uid_tarefa: str) -> list[Tarefa]:
    """Retorna as tarefas que têm a tarefa informada como predecessora direta — ou
    seja, dependem dela para começar. Usado para saber o que é impactado quando essa
    tarefa é concluída."""
    return [
        tarefa for tarefa in projeto.tarefas_detalhe
        if any(dep.predecessora_uid == uid_tarefa for dep in tarefa.dependencias)
    ]


def gerar_observacoes_simulacao(
    projeto: Projeto, uids_concluidas: list[str], idioma: str = "pt"
) -> list[str]:
    """Gera um texto descritivo por tarefa marcada como concluída na simulação de 'e
    se', explicando quais outras atividades são impactadas (sucessoras diretas que
    passam a poder começar) e se a tarefa concluída era crítica."""
    observacoes: list[str] = []
    tarefas_por_uid = {tarefa.uid: tarefa for tarefa in projeto.tarefas_detalhe}
    for uid in uids_concluidas:
        tarefa = tarefas_por_uid.get(uid)
        if tarefa is None:
            continue
        sucessoras = identificar_sucessoras_diretas(projeto, uid)
        if sucessoras:
            nomes_sucessoras = ", ".join(f"'{sucessora.nome}'" for sucessora in sucessoras)
            texto = tf(
                "Ao concluir '{nome}', {n} tarefa(s) sucessora(s) pode(m) ser iniciada(s): {sucessoras}.",
                idioma, nome=tarefa.nome, n=len(sucessoras), sucessoras=nomes_sucessoras,
            )
        else:
            texto = tf(
                "Ao concluir '{nome}', nenhuma outra tarefa depende diretamente dela no cronograma.",
                idioma, nome=tarefa.nome,
            )
        if tarefa.critica:
            texto += " " + t(
                "Como é uma tarefa crítica, isso também reduz o risco no caminho crítico do projeto.",
                idioma,
            )
        observacoes.append(texto)
    return observacoes


@dataclass
class ResultadoMonteCarlo:
    datas_simuladas: np.ndarray  # datetime64[ns], uma por rodada de simulação
    percentis: dict[int, date]   # ex.: {10: date(...), 50: date(...), 80: date(...), 90: date(...)}
    n_tarefas_simuladas: int


_NS_POR_DIA = 24 * 60 * 60 * 1_000_000_000


def _ordenar_topologicamente(tarefas: list[Tarefa]) -> list[str]:
    """Ordena as tarefas por dependência (predecessora antes de sucessora), via
    Kahn. Predecessoras que apontam para um uid fora do projeto (ou não presente na
    lista, ex.: tarefas-resumo) são ignoradas. Se houver um ciclo (dado inválido, não
    deveria acontecer num cronograma exportado corretamente), as tarefas do ciclo
    entram no fim, sem respeitar suas dependências — evita loop infinito."""
    uids = {t.uid for t in tarefas}
    sucessoras_de: dict[str, list[str]] = {uid: [] for uid in uids}
    grau_entrada: dict[str, int] = {uid: 0 for uid in uids}
    for tarefa in tarefas:
        preds_validas = {d.predecessora_uid for d in tarefa.dependencias if d.predecessora_uid in uids}
        grau_entrada[tarefa.uid] = len(preds_validas)
        for uid_pred in preds_validas:
            sucessoras_de[uid_pred].append(tarefa.uid)

    fila = [uid for uid, grau in grau_entrada.items() if grau == 0]
    ordem: list[str] = []
    grau_restante = dict(grau_entrada)
    while fila:
        uid = fila.pop()
        ordem.append(uid)
        for uid_suc in sucessoras_de[uid]:
            grau_restante[uid_suc] -= 1
            if grau_restante[uid_suc] == 0:
                fila.append(uid_suc)

    if len(ordem) < len(uids):
        vistos = set(ordem)
        ordem.extend(uid for uid in uids if uid not in vistos)
    return ordem


def simular_monte_carlo_termino(
    projeto: Projeto,
    data_status: date,
    n_simulacoes: int = 2000,
    fator_otimista: float = 0.8,
    fator_pessimista: float = 1.3,
    semente: int = 42,
) -> Optional[ResultadoMonteCarlo]:
    """Simulação de Monte Carlo da data de término do projeto — em vez de uma única
    previsão (ou 3 pontos fixos), roda `n_simulacoes` cenários variando a duração
    restante de cada tarefa ainda não concluída (distribuição triangular: otimista =
    `fator_otimista` x duração planejada, pessimista = `fator_pessimista` x) e propaga
    o efeito pelas dependências entre tarefas (Término-Início, Início-Início,
    Término-Término, Início-Término), tarefa por tarefa, na ordem topológica do grafo
    de dependências. Tarefas já 100% concluídas usam sua data real de término como
    âncora fixa (não são sorteadas). O resultado é a distribuição de datas de término
    do projeto entre todos os cenários — dela se lê, por exemplo, 'há 80% de chance de
    terminar até {P80}'.

    Limitação: como o programa não tem um motor de CPM completo, tarefas sem nenhuma
    predecessora mantêm a data de início atualmente agendada como âncora (não são
    reposicionadas) — só a duração é incerta."""
    tarefas = [t for t in projeto.tarefas_detalhe if t.termino is not None]
    if not tarefas:
        return None

    tarefas_por_uid = {t.uid: t for t in tarefas}
    ordem = _ordenar_topologicamente(tarefas)

    rng = np.random.default_rng(semente)
    ts_status = pd.Timestamp(data_status).value

    inicio_sim: dict[str, np.ndarray] = {}
    termino_sim: dict[str, np.ndarray] = {}

    for uid in ordem:
        tarefa = tarefas_por_uid[uid]

        if tarefa.percentual_concluido >= 100:
            termino_fixo = tarefa.termino_real or tarefa.termino
            inicio_fixo = tarefa.inicio_real or tarefa.inicio or termino_fixo
            inicio_sim[uid] = np.full(n_simulacoes, pd.Timestamp(inicio_fixo).value, dtype="int64")
            termino_sim[uid] = np.full(n_simulacoes, pd.Timestamp(termino_fixo).value, dtype="int64")
            continue

        ancora_inicio = tarefa.inicio_real or tarefa.inicio or data_status
        dias_restantes = max((tarefa.termino - max(ancora_inicio, data_status)).days, 1)

        preds_validas = [d for d in tarefa.dependencias if d.predecessora_uid in tarefas_por_uid]
        piso = max(pd.Timestamp(max(ancora_inicio, data_status)).value, ts_status)
        if preds_validas:
            candidatos = []
            deslocamento_ns = dias_restantes * _NS_POR_DIA
            for dep in preds_validas:
                p_inicio = inicio_sim[dep.predecessora_uid]
                p_termino = termino_sim[dep.predecessora_uid]
                if dep.tipo == 0:      # Término-Término
                    candidatos.append(p_termino - deslocamento_ns)
                elif dep.tipo == 2:    # Início-Término
                    candidatos.append(p_inicio - deslocamento_ns)
                elif dep.tipo == 3:    # Início-Início
                    candidatos.append(p_inicio)
                else:                  # Término-Início (padrão/mais comum)
                    candidatos.append(p_termino)
            inicio_efetivo = np.maximum(np.maximum.reduce(candidatos), piso)
        else:
            inicio_efetivo = np.full(n_simulacoes, piso, dtype="int64")

        # min/max sempre envolvem a moda (dias_restantes), mesmo que os fatores
        # informados estejam invertidos ou ambos do mesmo lado de 1.0 — a
        # distribuição triangular do numpy exige left <= mode <= right.
        minimo_dias = min(dias_restantes * fator_otimista, dias_restantes)
        maximo_dias = max(dias_restantes * fator_pessimista, dias_restantes)
        if np.isclose(minimo_dias, maximo_dias):
            # Sem variabilidade real (ex.: otimista == pessimista) — a triangular do
            # numpy exige limites estritamente diferentes; usa a duração fixa.
            duracao_amostrada = np.full(n_simulacoes, dias_restantes, dtype="float64")
        else:
            duracao_amostrada = rng.triangular(
                minimo_dias, dias_restantes, maximo_dias, size=n_simulacoes,
            )
        duracao_ns = np.clip(duracao_amostrada, 0.1, None) * _NS_POR_DIA

        inicio_sim[uid] = inicio_efetivo
        termino_sim[uid] = inicio_efetivo + duracao_ns.astype("int64")

    termino_projeto_ns = np.maximum.reduce(list(termino_sim.values()))
    datas_simuladas = pd.to_datetime(termino_projeto_ns).values

    percentis = {}
    for p in (10, 50, 80, 90):
        valor_ns = int(np.percentile(termino_projeto_ns, p))
        percentis[p] = pd.Timestamp(valor_ns).date()

    return ResultadoMonteCarlo(
        datas_simuladas=datas_simuladas,
        percentis=percentis,
        n_tarefas_simuladas=sum(1 for t in tarefas if t.percentual_concluido < 100),
    )


@dataclass
class ResultadoCorrenteCritica:
    buffer_dias: float
    percentual_buffer_consumido: float
    percentual_corrente_critica_concluida: float
    zona: str  # "verde", "amarela" ou "vermelha"
    origem_buffer: str  # "detectado" (tarefa de buffer já existe no arquivo) ou "sintetico" (via Monte Carlo)
    nome_tarefa_buffer: Optional[str]
    origem_corrente: str = "critica_ms_project"  # ou "cadeia_via_buffer"


def detectar_tarefa_buffer(projeto: Projeto) -> Optional[Tarefa]:
    """Procura uma tarefa cujo nome contenha 'buffer' ou 'pulmão' — prática comum de
    quem já modela Corrente Crítica dentro do MS Project como uma tarefa explícita
    (normalmente no fim da corrente crítica). Se houver mais de uma, usa a última
    (maior término), que costuma ser o buffer de projeto."""
    candidatas = [
        t for t in projeto.tarefas_detalhe
        if "buffer" in t.nome.lower() or "pulmão" in t.nome.lower() or "pulmao" in t.nome.lower()
    ]
    if not candidatas:
        return None
    return max(candidatas, key=lambda t: t.termino or date.min)


def _e_tarefa_buffer(tarefa: Tarefa) -> bool:
    nome = tarefa.nome.lower()
    return "buffer" in nome or "pulmão" in nome or "pulmao" in nome


def _identificar_cadeia_por_buffer(projeto: Projeto, tarefa_buffer: Tarefa) -> list[Tarefa]:
    """Reconstrói a corrente crítica andando para trás nas dependências a partir do
    buffer de projeto, para ferramentas de CCPM (como o Concerto) que não marcam
    tarefa.critica no cronograma — só inserem a tarefa de buffer no fim da cadeia.

    Para em qualquer tarefa cujo nome também pareça um buffer (feeding buffer de outra
    perna do cronograma) sem seguir para trás dela, já que essas alimentam a corrente
    crítica em um ponto específico mas pertencem a uma ramificação secundária, não à
    espinha dorsal principal que o buffer de projeto protege.
    """
    tarefas_por_uid = {t.uid: t for t in projeto.tarefas_detalhe}
    visitadas: set[str] = set()
    cadeia: list[Tarefa] = []
    fila = [dep.predecessora_uid for dep in tarefa_buffer.dependencias]
    while fila:
        uid = fila.pop()
        if uid in visitadas:
            continue
        visitadas.add(uid)
        tarefa = tarefas_por_uid.get(uid)
        if tarefa is None:
            continue
        cadeia.append(tarefa)
        if _e_tarefa_buffer(tarefa):
            continue
        fila.extend(dep.predecessora_uid for dep in tarefa.dependencias)
    return cadeia


def calcular_corrente_critica(
    projeto: Projeto,
    indicadores: Indicadores,
    resultado_monte_carlo: Optional[ResultadoMonteCarlo] = None,
) -> Optional[ResultadoCorrenteCritica]:
    """Calcula os dois números do 'gráfico de febre' (fever chart) da metodologia de
    Corrente Crítica (CCPM): quanto da corrente crítica já foi executado e quanto do
    buffer de projeto já foi consumido.

    Limitação: este programa não faz nivelamento de recursos, então 'corrente crítica'
    aqui é aproximada pelo caminho crítico já calculado pelo MS Project (tarefa.critica)
    — a corrente crítica de verdade poderia diferir quando há disputa de recursos entre
    tarefas não sequenciais.

    O buffer é obtido de duas formas: se o cronograma já tem uma tarefa nomeada como
    'buffer'/'pulmão' (prática comum de quem já modela CCPM dentro do MS Project), usa
    a duração e o % concluído dela diretamente. Caso contrário, sintetiza um buffer a
    partir da simulação de Monte Carlo (diferença entre P80 e P50 de término) e estima
    o consumo pelo atraso atual em relação a esse buffer.

    Quando nenhuma tarefa está marcada como crítica (comum em arquivos gerados por
    ferramentas de CCPM dedicadas, como o Concerto, que não usam o campo tradicional do
    MS Project) mas existe uma tarefa de buffer detectável, a corrente crítica é
    reconstruída andando para trás nas dependências a partir do buffer.
    """
    tarefas_criticas = [t for t in projeto.tarefas_detalhe if t.critica]
    origem_corrente = "critica_ms_project"
    tarefa_buffer_previa = None
    if not tarefas_criticas:
        tarefa_buffer_previa = detectar_tarefa_buffer(projeto)
        if tarefa_buffer_previa is None:
            return None
        tarefas_criticas = _identificar_cadeia_por_buffer(projeto, tarefa_buffer_previa)
        if not tarefas_criticas:
            return None
        origem_corrente = "cadeia_via_buffer"

    peso_total = sum((t.duracao_linha_base_horas or t.duracao_horas) for t in tarefas_criticas) or 1.0
    pct_concluido_cc = sum(
        t.percentual_concluido * (t.duracao_linha_base_horas or t.duracao_horas) for t in tarefas_criticas
    ) / peso_total

    tarefa_buffer = tarefa_buffer_previa or detectar_tarefa_buffer(projeto)
    if tarefa_buffer is not None:
        buffer_dias = (tarefa_buffer.duracao_linha_base_horas or tarefa_buffer.duracao_horas or 8.0) / 8.0
        pct_consumido = min(max(tarefa_buffer.percentual_concluido, 0.0), 100.0)
        origem = "detectado"
        nome_buffer = tarefa_buffer.nome
    elif resultado_monte_carlo is not None:
        p50 = resultado_monte_carlo.percentis[50]
        p80 = resultado_monte_carlo.percentis[80]
        buffer_dias = max((p80 - p50).days, 1)
        atraso_atual_dias = max(indicadores.atraso_dias, 0)
        pct_consumido = min(atraso_atual_dias / buffer_dias * 100, 100.0)
        origem = "sintetico"
        nome_buffer = None
    else:
        return None

    # Critério de zona simplificado (não é uma fórmula-padrão única na literatura de
    # CCPM — há variações entre autores): a tolerância ao consumo do buffer cresce à
    # medida que a corrente crítica avança, já que consumir buffer cedo no projeto é
    # mais grave do que perto do fim (menos tempo restante para se recuperar).
    limite_amarelo = (pct_concluido_cc / 100) * 66.7 + 10
    limite_vermelho = (pct_concluido_cc / 100) * 66.7 + 33.3
    if pct_consumido <= limite_amarelo:
        zona = "verde"
    elif pct_consumido <= limite_vermelho:
        zona = "amarela"
    else:
        zona = "vermelha"

    return ResultadoCorrenteCritica(
        buffer_dias=buffer_dias,
        percentual_buffer_consumido=pct_consumido,
        percentual_corrente_critica_concluida=pct_concluido_cc,
        zona=zona,
        origem_buffer=origem,
        nome_tarefa_buffer=nome_buffer,
        origem_corrente=origem_corrente,
    )
