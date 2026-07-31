from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

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


def calcular_status_geral(indicadores: Indicadores, idioma: str = "pt") -> tuple[str, str]:
    """Classifica o status geral do projeto em 'verde', 'amarelo' ou 'vermelho' a partir
    do SPI, do CPI e da quantidade de tarefas críticas atrasadas — o mesmo tipo de
    semáforo usado num report semanal de obra. Retorna (cor, descrição já traduzida)."""
    spi_critico = indicadores.spi is not None and indicadores.spi < 0.85
    cpi_critico = indicadores.cpi is not None and indicadores.cpi < 0.85
    spi_alerta = indicadores.spi is not None and indicadores.spi < 0.95
    cpi_alerta = indicadores.cpi is not None and indicadores.cpi < 0.95

    if spi_critico or cpi_critico or indicadores.tarefas_criticas_atrasadas >= 3:
        return "vermelho", t(
            "Obra com desvios relevantes de prazo e/ou custo — ação corretiva necessária.", idioma
        )
    if spi_alerta or cpi_alerta or indicadores.tarefas_criticas_atrasadas >= 1:
        return "amarelo", t(
            "Obra com desvios pontuais, já identificados e em monitoramento.", idioma
        )
    return "verde", t(
        "Obra dentro do planejado, com desvios controlados e sob monitoramento.", idioma
    )


def sugerir_avancos_semana(
    projeto: Projeto,
    data_status: date,
    dias_janela: int = 7,
    top_n: int = 3,
    idioma: str = "pt",
) -> list[str]:
    """Sugere textos para 'principais avanços da semana': primeiro as tarefas concluídas
    (100%) com término real dentro da janela e, se não houver o suficiente, completa com
    as tarefas em andamento mais próximas da conclusão. Serve só de ponto de partida —
    o texto final fica num campo editável pelo usuário."""
    inicio_semana = data_status - timedelta(days=dias_janela - 1)
    concluidas = sorted(
        (
            tarefa for tarefa in projeto.tarefas_detalhe
            if tarefa.percentual_concluido >= 100
            and tarefa.termino_real is not None
            and inicio_semana <= tarefa.termino_real <= data_status
        ),
        key=lambda tarefa: tarefa.termino_real,
        reverse=True,
    )
    sugestoes = [
        tf("{nome} concluída – 100%", idioma, nome=tarefa.nome) for tarefa in concluidas[:top_n]
    ]
    if len(sugestoes) < top_n:
        em_andamento = sorted(
            (tarefa for tarefa in projeto.tarefas_detalhe if 0 < tarefa.percentual_concluido < 100),
            key=lambda tarefa: tarefa.percentual_concluido,
            reverse=True,
        )
        for tarefa in em_andamento:
            texto = tf(
                "{nome} – {pct:.0f}% concluído", idioma, nome=tarefa.nome, pct=tarefa.percentual_concluido
            )
            if texto not in sugestoes:
                sugestoes.append(texto)
            if len(sugestoes) >= top_n:
                break
    return sugestoes
