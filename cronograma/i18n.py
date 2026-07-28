"""Suporte bilíngue (português/inglês) para a interface do programa.

Design: os textos são escritos em português no código (chave = texto em si), e
'TRADUCOES' mapeia cada um para o inglês. Use t() para textos estáticos e tf()
para textos com parâmetros (estilo str.format). Se o idioma for português, ou se
não houver tradução cadastrada, o texto original em português é retornado — ou
seja, esquecer de traduzir algo nunca quebra o app, só deixa aquele texto em PT.
"""

from datetime import date


def t(texto: str, idioma: str) -> str:
    """Traduz um texto estático (sem parâmetros)."""
    if idioma != "en":
        return texto
    return TRADUCOES.get(texto, texto)


def tf(template_pt: str, idioma: str, **kwargs) -> str:
    """Traduz um texto com parâmetros. 'template_pt' é o modelo em português com
    placeholders {chave}; a tradução (se existir) deve usar os mesmos placeholders."""
    modelo = template_pt if idioma != "en" else TRADUCOES.get(template_pt, template_pt)
    return modelo.format(**kwargs)


def formatar_data(d: date | None, idioma: str) -> str:
    if d is None:
        return "N/A" if idioma == "en" else "N/D"
    return d.strftime("%m/%d/%Y") if idioma == "en" else d.strftime("%d/%m/%Y")


def formato_coluna_data(idioma: str) -> str:
    """Formato para st.column_config.DateColumn."""
    return "MM/DD/YYYY" if idioma == "en" else "DD/MM/YYYY"


TRADUCOES: dict[str, str] = {
    # --- Barra lateral / topo ---
    "📁 Cronograma": "📁 Schedule",
    "Envie o(s) arquivo(s) do cronograma": "Upload the schedule file(s)",
    "Arquivo .mpp do MS Project, ou .xml exportado via Arquivo > Salvar Como > XML. "
    "Envie mais de um arquivo para ver a aba de Portfólio.":
        "MS Project .mpp file, or .xml exported via File > Save As > XML. "
        "Upload more than one file to see the Portfolio tab.",
    "Não foi possível ler o arquivo {nome}: {erro}": "Could not read the file {nome}: {erro}",
    "Ocorreu um erro inesperado ao ler o arquivo {nome}: {erro}": "An unexpected error occurred while reading the file {nome}: {erro}",
    "📊 Dashboard de Cronograma de Projeto": "📊 Project Schedule Dashboard",
    "👈 Envie um arquivo **.xml** (exportado do MS Project) ou **.mpp** na barra lateral para começar.\n\n"
    "Para exportar o XML no MS Project: **Arquivo > Salvar Como**, escolha o tipo **XML**.":
        "👈 Upload an **.xml** file (exported from MS Project) or **.mpp** in the sidebar to get started.\n\n"
        "To export the XML from MS Project: **File > Save As**, choose the **XML** type.",
    "Projeto para detalhamento": "Project for detail view",
    "**Detalhando o projeto:** {v}": "**Showing details for:** {v}",
    "Data de status (para cálculo dos indicadores)": "Status date (used to calculate indicators)",
    "**Início:** {v}": "**Start:** {v}",
    "**Término:** {v}": "**Finish:** {v}",
    "**Data de status:** {v}": "**Status date:** {v}",
    "**Linhas de base salvas:** {v}": "**Saved baselines:** {v}",
    "**Linha de base ativa:** {v}": "**Active baseline:** {v}",
    "{inicio} a {termino}": "{inicio} to {termino}",
    "🧹 Limpar filtro de datas": "🧹 Clear date filter",
    "Idioma": "Language",

    # --- Abas ---
    "📊 Portfólio": "📊 Portfolio",
    "📈 Resumo": "📈 Summary",
    "📉 Curva S": "📉 S-Curve",
    "✅ Tarefas": "✅ Tasks",
    "📅 Gantt": "📅 Gantt",
    "📋 Checklist de Qualidade": "📋 Quality Checklist",
    "👥 Recursos": "👥 Resources",
    "📤 Exportar": "📤 Export",

    # --- Portfólio ---
    "Portfólio de Projetos": "Project Portfolio",
    "Data de status": "Status date",
    "Linha de Base Ativa": "Active Baseline",
    "Projetos": "Projects",
    "Projetos Atrasados": "Delayed Projects",
    "Tarefas Atrasadas": "Delayed Tasks",
    "Críticas Atrasadas": "Delayed Critical",
    "Tarefas Críticas Atrasadas": "Delayed Critical Tasks",
    "Comparativo entre Projetos": "Project Comparison",
    "Projeto": "Project",
    "Total de Tarefas": "Total Tasks",
    "Curva S Consolidada do Portfólio": "Consolidated Portfolio S-Curve",
    "Exportar Relatório do Portfólio": "Export Portfolio Report",
    "Não foi possível gerar a Curva S consolidada (sem dados de valor nos projetos).":
        "Could not generate the consolidated S-Curve (no value data in the projects).",
    "Ocultar nomes dos projetos no indicador de término": "Hide project names in the finish-date indicator",
    "As linhas pontilhadas verticais marcam o término (atual) de cada projeto.":
        "The vertical dotted lines mark the (current) finish date of each project.",
    "ℹ️ Como a Curva S do Portfólio foi calculada": "ℹ️ How the Portfolio S-Curve was calculated",
    "Cada projeto é normalizado para % do seu próprio valor total (custo, "
    "ou duração quando não há custo) antes de ser combinado — isso permite somar "
    "cronogramas com unidades diferentes. A curva final é a média dessas curvas em "
    "%, ponderada pelo peso de cada projeto (duração total das tarefas), listado abaixo:":
        "Each project is normalized to % of its own total value (cost, "
        "or duration when there is no cost) before being combined — this allows adding up "
        "schedules with different units. The final curve is the average of these % curves, "
        "weighted by each project's weight (total task duration), listed below:",
    "Peso no Portfólio": "Portfolio Weight",

    # --- Resumo ---
    "% Concluído": "% Complete",
    "Atraso": "Delay",
    "{n} dia(s)": "{n} day(s)",
    "Principais Percepções": "Key Insights",
    "Tarefas Atrasadas ({n})": "Delayed Tasks ({n})",
    "Tarefa": "Task",
    "Crítica": "Critical",
    "Início": "Start",
    "Término": "Finish",
    "Término (linha de base)": "Finish (baseline)",
    "Atraso (dias)": "Delay (days)",
    "Sim": "Yes",
    "Não": "No",
    "Nenhuma tarefa está atrasada em relação à linha de base.": "No task is delayed relative to the baseline.",
    "Custo Real (AC)": "Actual Cost (AC)",
    "Trabalho Real (AC)": "Actual Work (AC)",
    "Custo Previsto ao Término (EAC)": "Estimate at Completion (EAC)",
    "Trabalho Previsto ao Término (EAC)": "Estimated Work at Completion (EAC)",
    "Resumo Financeiro": "Financial Summary",
    "Resumo de Trabalho": "Work Summary",
    "Métrica": "Metric",
    "Valor": "Value",
    "Valor Planejado (PV)": "Planned Value (PV)",
    "Valor Agregado (EV)": "Earned Value (EV)",
    "N/D": "N/A",

    # --- Curva S ---
    "Curva S — Linha de Base x Realizado/Previsto": "S-Curve — Baseline vs Actual/Forecast",
    "Ocultar aviso sobre unidade de medida": "Hide unit-of-measure notice",
    "ℹ️ Este arquivo não tem custos de recursos preenchidos no MS Project. "
    "Os indicadores e a Curva S abaixo foram calculados usando **horas de duração** "
    "(planejada x realizada) como proxy de valor, em vez de custo em R$.":
        "ℹ️ This file has no resource costs filled in on MS Project. "
        "The indicators and S-Curve below were calculated using **duration hours** "
        "(planned x actual) as a proxy for value, instead of cost.",
    "Dados disponíveis apenas para {data}.": "Data available only for {data}.",
    "Filtrar por data": "Filter by date",
    "Exibir em %": "Show as %",
    "Eixo horizontal": "Horizontal axis",
    "Ano": "Year",
    "Mês": "Month",
    "% Concluído (acumulado)": "% Complete (cumulative)",
    "Custo acumulado (R$)": "Cumulative cost ($)",
    "Trabalho acumulado (horas)": "Cumulative work (hours)",
    "Linha de Base": "Baseline",
    "Realizado / Previsto": "Actual / Forecast",
    "Data de status": "Status date",
    "Data": "Date",
    "Série": "Series",
    "'Linha de Base' distribui o {unidade} planejado de cada tarefa entre o Início e Término da linha de base. "
    "'Realizado / Previsto' mostra o progresso real (% concluído de cada tarefa) até a data de status e, "
    "a partir dali, segue o ritmo do cronograma atual (já com atrasos/replanejamentos) até o fim do projeto. "
    "O ponto na data de status bate exatamente com o card \"% Concluído\" do Resumo.":
        "'Baseline' spreads each task's planned {unidade} between the baseline Start and Finish. "
        "'Actual / Forecast' shows real progress (% complete of each task) up to the status date and, "
        "from there, follows the pace of the current schedule (already reflecting delays/replans) until the project ends. "
        "The point at the status date matches exactly the \"% Complete\" card on the Summary tab.",
    "custo": "cost",
    "duração (em horas)": "duration (in hours)",

    # --- Tarefas ---
    "Tarefas": "Tasks",
    "Mostrar apenas tarefas atrasadas": "Show only delayed tasks",
    "Mostrar apenas tarefas críticas": "Show only critical tasks",
    "🟪 Roxo = tarefa crítica · 🟥 Vermelho = atrasada · Vermelho mais forte = crítica e atrasada.":
        "🟪 Purple = critical task · 🟥 Red = delayed · Stronger red = critical and delayed.",
    "⬇️ Baixar relatório de tarefas (Excel)": "⬇️ Download tasks report (Excel)",
    "Planejado x Executado por período": "Planned vs Executed by period",
    "Não há datas suficientes no arquivo para montar o filtro por período.":
        "There aren't enough dates in the file to build the period filter.",
    "Planejadas no período ({n})": "Planned in the period ({n})",
    "Tarefas cujo cronograma atual (Início/Término vigentes) cruza o período selecionado.":
        "Tasks whose current schedule (current Start/Finish) overlaps the selected period.",
    "Executadas no período ({n})": "Executed in the period ({n})",
    "Tarefas com Início Real e Término Real registrados (já concluídas) que cruzam o período selecionado.":
        "Tasks with Actual Start and Actual Finish recorded (already completed) that overlap the selected period.",
    "⬇️ Baixar planejadas (Excel)": "⬇️ Download planned (Excel)",
    "⬇️ Baixar executadas (Excel)": "⬇️ Download executed (Excel)",
    "Início Real": "Actual Start",
    "Término Real": "Actual Finish",

    # --- Gantt ---
    "Gráfico de Gantt": "Gantt Chart",
    "Buscar tarefa pelo nome": "Search task by name",
    "Somente críticas": "Critical only",
    "Somente atrasadas": "Delayed only",
    "Filtrar por data (Início/Término cruzando o período)": "Filter by date (Start/Finish overlapping the period)",
    "Concluída": "Completed",
    "No prazo": "On track",
    "Atrasada": "Delayed",
    "Crítica atrasada": "Critical delayed",
    "Nenhuma tarefa encontrada com os filtros selecionados (ou sem datas de início/término).":
        "No task found with the selected filters (or missing start/finish dates).",
    "Status": "Status",
    "{status} (marco)": "{status} (milestone)",
    "A linha pontilhada vertical marca a Data de status ({data}).":
        "The vertical dotted line marks the Status date ({data}).",
    "Exibindo {n} tarefa(s). Losangos representam marcos; o número dentro das barras é o % concluído. "
    "Setas cinzas indicam dependências entre tarefas (só aparecem quando predecessora e sucessora estão "
    "ambas visíveis com os filtros atuais). Use os filtros acima para reduzir a lista em projetos grandes.":
        "Showing {n} task(s). Diamonds represent milestones; the number inside the bars is the % complete. "
        "Gray arrows indicate dependencies between tasks (they only show when both predecessor and successor are "
        "visible with the current filters). Use the filters above to shorten the list on large projects.",
    "Marco": "Milestone",
    "Predecessoras": "Predecessors",
    "⬇️ Baixar relatório do Gantt (Excel)": "⬇️ Download Gantt report (Excel)",

    # --- Checklist ---
    "Checklist de Qualidade do Cronograma": "Schedule Quality Checklist",
    "Itens avaliados automaticamente a partir dos dados do arquivo.":
        "Items assessed automatically from the file's data.",
    "Pontuação": "Score",
    "Cada item vale até 2 pontos (Conforme = 2, Parcial = 1, Não Conforme = 0). "
    "{avaliados} de {total} itens contam na pontuação — os demais ficaram "
    "'N/A' e não entram no total, por isso o máximo é {maximo} (não {total_x2}).":
        "Each item is worth up to 2 points (Compliant = 2, Partial = 1, Non-compliant = 0). "
        "{avaliados} of {total} items count toward the score — the rest were "
        "'N/A' and are excluded from the total, which is why the maximum is {maximo} (not {total_x2}).",
    "Percentual": "Percentage",
    "Maturidade": "Maturity",
    "{avaliados} de {total} itens contam na pontuação.":
        "{avaliados} of {total} items count toward the score.",
    "Tarefas: {lista}": "Tasks: {lista}",
    "(e mais {n} tarefa(s))": "(and {n} more task(s))",
    "Tabela de classificação de maturidade": "Maturity classification table",
    "Abaixo de 50%": "Below 50%",
    "Excelente": "Excellent",
    "Muito bom": "Very good",
    "Adequado, com melhorias": "Adequate, needs improvement",
    "Baixa maturidade": "Low maturity",
    "Cronograma inadequado para controle": "Schedule unsuitable for control",
    "Conforme": "Compliant",
    "Parcial": "Partial",
    "Não Conforme": "Non-compliant",
    "N/A": "N/A",
    "⬇️ Baixar checklist (Excel)": "⬇️ Download checklist (Excel)",
    "Seção": "Section",
    "Item": "Item",
    "Evidência": "Evidence",

    # --- Recursos ---
    "Recursos": "Resources",
    "O arquivo não contém informações de recursos.": "The file does not contain resource information.",
    "Custo": "Cost",
    "Custo por Recurso": "Cost by Resource",
    "Custo (R$)": "Cost ($)",
    "Trabalho (horas)": "Work (hours)",
    "Trabalho por Recurso": "Work by Resource",
    "Horas": "Hours",
    "Recurso": "Resource",

    # --- Exportar ---
    "Exportar Relatórios": "Export Reports",
    "Gere um relatório com o resumo, indicadores, tarefas e a curva S do projeto.":
        "Generate a report with the project's summary, indicators, tasks and S-curve.",
    "⬇️ Baixar Excel": "⬇️ Download Excel",
    "⬇️ Baixar PDF": "⬇️ Download PDF",
    "Relatório Executivo por Período": "Executive Report by Period",
    "Gere um PDF pronto para apresentação com os indicadores, a Curva S, o Gráfico de Gantt "
    "e a lista de atividades filtrados por um período específico.":
        "Generate a presentation-ready PDF with the indicators, S-Curve, Gantt Chart "
        "and the activity list filtered by a specific period.",
    "Selecione o período do relatório": "Select the report period",
    "{n} tarefa(s) encontradas no período selecionado.": "{n} task(s) found in the selected period.",
    "⬇️ Baixar Relatório Executivo (PDF)": "⬇️ Download Executive Report (PDF)",
    "Não há tarefas com datas suficientes para gerar o relatório executivo.":
        "There aren't enough tasks with dates to generate the executive report.",

    # --- Percepções (metricas.py) ---
    "Não foi possível calcular o SPI (índice de prazo) porque o arquivo não contém dados de linha de base (baseline).":
        "Could not calculate SPI (schedule performance index) because the file has no baseline data.",
    "O projeto está atrasado em relação ao planejado (SPI = {spi:.2f}). "
    "O progresso real está abaixo do progresso previsto para a data de status.":
        "The project is behind schedule (SPI = {spi:.2f}). "
        "Actual progress is below the progress expected for the status date.",
    "O projeto está adiantado em relação ao planejado (SPI = {spi:.2f}).":
        "The project is ahead of schedule (SPI = {spi:.2f}).",
    "O projeto está dentro do prazo planejado (SPI = {spi:.2f}).":
        "The project is on schedule (SPI = {spi:.2f}).",
    "SV (variância de prazo) = {sv}. Valor negativo indica que o valor agregado (EV) "
    "está abaixo do planejado (PV) até a data de status — o projeto está atrasado.":
        "SV (schedule variance) = {sv}. A negative value indicates that earned value (EV) "
        "is below planned value (PV) as of the status date — the project is behind schedule.",
    "SV (variância de prazo) = {sv}. Valor positivo indica que o valor agregado (EV) "
    "está acima do planejado (PV) até a data de status — o projeto está adiantado.":
        "SV (schedule variance) = {sv}. A positive value indicates that earned value (EV) "
        "is above planned value (PV) as of the status date — the project is ahead of schedule.",
    "SV (variância de prazo) = 0. O projeto está exatamente em dia com o planejado.":
        "SV (schedule variance) = 0. The project is exactly on track with the plan.",
    "não há custos reais (ActualCost) registrados": "there are no actual costs (ActualCost) recorded",
    "não há duração real (ActualDuration) registrada": "there is no actual duration (ActualDuration) recorded",
    "Não foi possível calcular o {rotulo} porque {motivo}.": "Could not calculate {rotulo} because {motivo}.",
    "O custo real está acima do orçado ({rotulo} = {cpi:.2f}). "
    "Se essa tendência continuar, o projeto deve estourar o orçamento.":
        "Actual cost is above budget ({rotulo} = {cpi:.2f}). "
        "If this trend continues, the project is likely to go over budget.",
    "As tarefas estão consumindo mais tempo do que o planejado ({rotulo} = {cpi:.2f}).":
        "Tasks are taking more time than planned ({rotulo} = {cpi:.2f}).",
    "O projeto está custando menos do que o orçado até o momento ({rotulo} = {cpi:.2f}).":
        "The project is costing less than budgeted so far ({rotulo} = {cpi:.2f}).",
    "As tarefas estão sendo concluídas com menos tempo do que o planejado ({rotulo} = {cpi:.2f}).":
        "Tasks are being completed in less time than planned ({rotulo} = {cpi:.2f}).",
    "O custo real está alinhado com o orçamento planejado ({rotulo} = {cpi:.2f}).":
        "Actual cost is aligned with the planned budget ({rotulo} = {cpi:.2f}).",
    "O tempo realizado está alinhado com o planejado ({rotulo} = {cpi:.2f}).":
        "Actual time is aligned with the plan ({rotulo} = {cpi:.2f}).",
    "A data de término projetada está {n} dia(s) além da data de término da linha de base.":
        "The projected finish date is {n} day(s) beyond the baseline finish date.",
    "A data de término projetada está {n} dia(s) antes da linha de base.":
        "The projected finish date is {n} day(s) ahead of the baseline.",
    "Existem {n} tarefa(s) crítica(s) atrasada(s), "
    "o que representa risco direto para a data final do projeto.":
        "There are {n} delayed critical task(s), "
        "which poses a direct risk to the project's final date.",
    "No total, {n} de {total} tarefas "
    "estão atrasadas em relação à linha de base.":
        "In total, {n} of {total} tasks "
        "are delayed relative to the baseline.",
    "Progresso geral do projeto: {pct:.1f}% concluído.": "Overall project progress: {pct:.1f}% complete.",
    "Mudança de planejamento em '{nome}': término foi de "
    "{data_base} (linha de base) para {data_atual} (atual) "
    "— {direcao} de {n} dia(s).":
        "Planning change in '{nome}': finish went from "
        "{data_base} (baseline) to {data_atual} (current) "
        "— {direcao} of {n} day(s).",
    "atraso": "delay",
    "adiantamento": "advance",
    "CPI (índice de custo)": "CPI (cost performance index)",
    "CPI (índice de eficiência de prazo trabalhado)": "CPI (worked-schedule efficiency index)",

    # --- Checklist: seções ---
    "1. Estrutura do Cronograma (WBS)": "1. Schedule Structure (WBS)",
    "2. Atividades": "2. Activities",
    "3. Relacionamentos": "3. Relationships",
    "4. Restrições": "4. Constraints",
    "5. Recursos": "5. Resources",
    "6. Custos (quando utilizados)": "6. Costs (when used)",
    "7. Linha de Base (Baseline)": "7. Baseline",
    "8. Caminho Crítico": "8. Critical Path",
    "9. Atualização": "9. Status Update",
    "10. Indicadores": "10. Indicators",
    "11. Qualidade do Planejamento": "11. Planning Quality",
    "12. Governança": "12. Governance",
    "13. Auditoria Final": "13. Final Audit",

    # --- Checklist: seção 1 ---
    "Existe uma Estrutura Analítica do Projeto (EAP/WBS).": "There is a Work Breakdown Structure (WBS).",
    "As atividades estão organizadas em fases.": "Activities are organized into phases.",
    "Não existem atividades órfãs.": "There are no orphan activities.",
    "Hierarquia de níveis (OutlineLevel) encontrada no arquivo.": "Level hierarchy (OutlineLevel) found in the file.",
    "Nenhuma hierarquia de níveis encontrada.": "No level hierarchy found.",
    "Tarefas-resumo (fases/grupos) encontradas.": "Summary tasks (phases/groups) found.",
    "Nenhuma tarefa-resumo encontrada no arquivo.": "No summary task found in the file.",
    "{n} de {total} tarefas sem predecessora e sem sucessora.": "{n} of {total} tasks with no predecessor and no successor.",

    # --- Checklist: seção 2 ---
    "Todas as atividades possuem duração.": "All activities have a duration.",
    "{n} de {total} tarefas (não-marco) sem duração.": "{n} of {total} tasks (non-milestone) without duration.",
    "Não existem atividades com duração negativa.": "There are no activities with negative duration.",
    "{n} tarefa(s) com duração negativa.": "{n} task(s) with negative duration.",
    "Não existem atividades excessivamente longas (ex.: >20 dias).": "There are no excessively long activities (e.g., >20 days).",
    "{n} de {total} tarefas com duração acima de 20 dias úteis (assumindo 8h/dia).": "{n} of {total} tasks with duration above 20 working days (assuming 8h/day).",
    "Não existem atividades excessivamente curtas sem necessidade.": "There are no unnecessarily short activities.",
    "{n} de {total} tarefas com menos de 1 hora de duração (avalie se fazem sentido).": "{n} of {total} tasks with less than 1 hour of duration (assess whether they make sense).",
    "Os marcos possuem duração zero.": "Milestones have zero duration.",
    "{n} de {total_marcos} marcos com duração diferente de zero.": "{n} of {total_marcos} milestones with duration other than zero.",
    "Nenhum marco encontrado no arquivo.": "No milestone found in the file.",

    # --- Checklist: seção 3 ---
    "Todas as atividades possuem predecessora.": "All activities have a predecessor.",
    "{n} de {total} tarefas sem predecessora (a primeira tarefa do cronograma normalmente não tem).": "{n} of {total} tasks without a predecessor (the first task in the schedule normally doesn't have one).",
    "Todas possuem sucessora (exceto a última).": "All have a successor (except the last one).",
    "{n} de {total} tarefas sem sucessora (a última tarefa do cronograma normalmente não tem).": "{n} of {total} tasks without a successor (the last task in the schedule normally doesn't have one).",
    "Não existem atividades soltas.": "There are no disconnected activities.",
    "{n} de {total} tarefas sem predecessora E sem sucessora ao mesmo tempo.": "{n} of {total} tasks with no predecessor AND no successor at the same time.",
    "Não existem relacionamentos redundantes.": "There are no redundant relationships.",
    "{n} vínculo(s) duplicado(s) encontrado(s).": "{n} duplicate link(s) found.",

    # --- Checklist: seção 4 ---
    "As atividades utilizam ASAP (As Soon As Possible) sempre que possível.": "Activities use ASAP (As Soon As Possible) whenever possible.",
    "{n} de {total} tarefas com restrição diferente de ASAP.": "{n} of {total} tasks with a constraint other than ASAP.",
    "Não existem restrições rígidas desnecessárias (Must Start On / Must Finish On).": "There are no unnecessary hard constraints (Must Start On / Must Finish On).",
    "{n} de {total} tarefas com restrição rígida (MSO/MFO).": "{n} of {total} tasks with a hard constraint (MSO/MFO).",
    "Datas foram controladas pelo vínculo e não digitadas manualmente.": "Dates were driven by dependencies, not manually typed.",
    "{n} de {total} tarefas em modo de agendamento manual.": "{n} of {total} tasks in manual scheduling mode.",

    # --- Checklist: seção 5 ---
    "Todas as atividades possuem responsável.": "All activities have an owner.",
    "{n} de {total} tarefas (não-marco) sem recurso atribuído.": "{n} of {total} tasks (non-milestone) without an assigned resource.",
    "Não existem recursos duplicados.": "There are no duplicate resources.",
    "{n} nome(s) de recurso duplicado(s) de {total} recurso(s).": "{n} duplicate resource name(s) out of {total} resource(s).",

    # --- Checklist: seção 6 ---
    "Recursos possuem custo.": "Resources have a cost.",
    "{n} de {total} recursos sem custo definido.": "{n} of {total} resources without a defined cost.",
    "Arquivo não tem custos de recursos preenchidos.": "The file has no resource costs filled in.",
    "Baseline de custo foi salva.": "Cost baseline was saved.",
    "Custo de linha de base encontrado.": "Baseline cost found.",
    "Nenhum custo de linha de base encontrado.": "No baseline cost found.",

    # --- Checklist: seção 7 ---
    "Baseline foi salva.": "Baseline was saved.",
    "{n} de {total} tarefas com linha de base identificada.": "{n} of {total} tasks with an identified baseline.",
    "Data inicial da baseline existe.": "Baseline start date exists.",
    "{n} de {total} tarefas com Início (linha de base).": "{n} of {total} tasks with a Start (baseline).",
    "Data final da baseline existe.": "Baseline finish date exists.",
    "{n} de {total} tarefas com Término (linha de base).": "{n} of {total} tasks with a Finish (baseline).",
    "Trabalho (duração) baseline registrado.": "Baseline work (duration) recorded.",
    "Duração de linha de base encontrada.": "Baseline duration found.",
    "Nenhuma duração de linha de base encontrada.": "No baseline duration found.",
    "Custo baseline registrado.": "Baseline cost recorded.",

    # --- Checklist: seção 8 ---
    "Caminho crítico identificado.": "Critical path identified.",
    "{n} de {total} tarefas marcadas como críticas.": "{n} of {total} tasks marked as critical.",
    "Float Total (folga) foi analisado.": "Total Float (slack) was analyzed.",
    "Folga total disponível em {n} de {total} tarefas.": "Total float available in {n} of {total} tasks.",
    "Folga total não encontrada no arquivo.": "Total float not found in the file.",
    "Folgas negativas foram investigadas.": "Negative floats were investigated.",
    "{n} tarefa(s) com folga total negativa.": "{n} task(s) with negative total float.",
    "N/A — folga total não disponível no arquivo.": "N/A — total float not available in the file.",

    # --- Checklist: seção 9 ---
    "Data de Status definida.": "Status Date defined.",
    "Data de status: {data}": "Status date: {data}",
    "Nenhuma data de status encontrada.": "No status date found.",
    "Progresso atualizado.": "Progress updated.",
    "Ao menos uma tarefa com % concluído maior que zero.": "At least one task with % complete greater than zero.",
    "Nenhuma tarefa com progresso registrado.": "No task with recorded progress.",
    "% Completo coerente com a data de status.": "% Complete consistent with the status date.",
    "{n} de {total} tarefas com início futuro (após a data de status) e progresso maior que zero.": "{n} of {total} tasks with a future start (after the status date) and progress greater than zero.",
    "Atividades concluídas possuem data real de término.": "Completed activities have an actual finish date.",
    "{n} de {total_concluidas} tarefas concluídas sem Término Real registrado.": "{n} of {total_concluidas} completed tasks without a recorded Actual Finish.",
    "Atividades futuras não possuem progresso indevido.": "Future activities have no undue progress.",
    "{n} de {total} tarefas com início futuro e progresso indevido.": "{n} of {total} tasks with a future start and undue progress.",

    # --- Checklist: seção 10 ---
    "SPI calculado.": "SPI calculated.",
    "SPI não pôde ser calculado (sem baseline).": "SPI could not be calculated (no baseline).",
    "CPI calculado (quando aplicável).": "CPI calculated (when applicable).",
    "CPI não pôde ser calculado.": "CPI could not be calculated.",
    "Percentual físico atualizado.": "Physical percentage updated.",
    "% Concluído geral do projeto: {pct:.1f}%.": "Overall project % Complete: {pct:.1f}%.",
    "Percentual financeiro atualizado.": "Financial percentage updated.",
    "Custo Real acumulado: {ac:,.2f}.": "Cumulative Actual Cost: {ac:,.2f}.",
    "Curva S disponível.": "S-Curve available.",
    "Gerada automaticamente na aba Curva S deste programa.": "Automatically generated in this program's S-Curve tab.",

    # --- Checklist: seção 11 ---
    "Não existem tarefas manuais.": "There are no manually scheduled tasks.",
    "{n} de {total} tarefas em modo manual.": "{n} of {total} tasks in manual mode.",
    "Todas as tarefas estão em modo automático.": "All tasks are in automatic mode.",
    "{n} de {total} tarefas em modo automático.": "{n} of {total} tasks in automatic mode.",
    "Não existem datas digitadas manualmente (restrições diferentes de ASAP).": "There are no manually typed dates (constraints other than ASAP).",
    "Não existem atividades duplicadas.": "There are no duplicate activities.",
    "{n} nome(s) de tarefa duplicado(s) de {total}.": "{n} duplicate task name(s) out of {total}.",
    "Não existem durações muito elevadas.": "There are no excessively high durations.",
    "{n} de {total} tarefas com duração acima de 20 dias úteis.": "{n} of {total} tasks with duration above 20 working days.",

    # --- Checklist: seção 12 ---
    "Código WBS preenchido.": "WBS code filled in.",
    "{n} de {total} tarefas com código WBS preenchido.": "{n} of {total} tasks with a WBS code filled in.",
    "ID da atividade definido.": "Activity ID defined.",
    "Todas as tarefas possuem ID único atribuído pelo MS Project.": "All tasks have a unique ID assigned by MS Project.",
    "Responsável informado.": "Owner informed.",
    "Fase do projeto definida.": "Project phase defined.",
    "Tarefas-resumo (fases) encontradas.": "Summary tasks (phases) found.",
    "Nenhuma tarefa-resumo encontrada.": "No summary task found.",

    # --- Checklist: seção 13 ---
    "Não existem atividades sem predecessor.": "There are no activities without a predecessor.",
    "Não existem atividades sem sucessor (exceto a última).": "There are no activities without a successor (except the last one).",
    "{n} de {total} tarefas sem predecessora.": "{n} of {total} tasks without a predecessor.",
    "{n} de {total} tarefas sem sucessora.": "{n} of {total} tasks without a successor.",
    "Não existem restrições indevidas.": "There are no undue constraints.",
    "Baseline salva.": "Baseline saved.",
    "Data de Status atualizada.": "Status Date updated.",
}
