# 📊 Dashboard de Cronograma de Projeto

Aplicativo web (Streamlit) para analisar cronogramas de projeto exportados do **MS Project**, calcular indicadores de valor agregado (EVM), gerar Curva S, Gráfico de Gantt, checklist de qualidade e relatórios — para um único projeto ou uma visão consolidada de **portfólio** com vários projetos ao mesmo tempo.

Disponível em português e inglês.

## Funcionalidades

### Leitura de cronogramas
- Upload de arquivos **.xml** (exportado do MS Project via *Arquivo > Salvar Como > XML*) — funciona em qualquer ambiente, inclusive na nuvem.
- Upload de arquivos **.mpp** nativos — requer Java e a biblioteca `mpxj` instalados localmente (não funciona no Streamlit Community Cloud).
- Suporte a múltiplos arquivos ao mesmo tempo, habilitando a visão de portfólio.

### Indicadores (EVM)
- SPI, CPI, % concluído, variação de prazo (SV) e de custo (CV), atraso em dias.
- Funciona mesmo sem dados de custo preenchidos, usando duração/trabalho como proxy de valor.
- Percepções automáticas em linguagem natural (atrasos, mudanças de planejamento, riscos).

### Curva S
- Compara **Linha de Base** x **Realizado/Previsto**, com marcação da data de status.
- Filtro de período sincronizado com as demais abas, alternância de eixo por ano/mês, exibição em % ou em valor absoluto.

### Tarefas
- Tabela completa com destaque visual para tarefas críticas e atrasadas.
- Filtro "Planejado x Executado" por período, com exportação em Excel.

### Gráfico de Gantt
- Barras coloridas por status (no prazo, atrasada, crítica, crítica atrasada, concluída), marcos como losangos.
- Setas de dependência entre tarefas, filtro por texto/criticidade/atraso/período, eixo de datas duplicado (topo e base).

### Checklist de Qualidade do Cronograma
- ~50 verificações automáticas (estrutura, atividades, relacionamentos, restrições, recursos, custos, baseline, caminho crítico, atualização, indicadores, governança) avaliadas diretamente a partir dos dados do arquivo.
- Evidências indicam quais tarefas específicas causam cada não conformidade (ex.: quais estão sem predecessora).
- Pontuação e classificação de maturidade (Excelente, Muito bom, Adequado, Baixa maturidade, Inadequado).

### Portfólio (múltiplos projetos)
- Números consolidados (ponderados pelo tamanho de cada cronograma): % concluído, SPI, CPI, projetos atrasados, tarefas atrasadas/críticas.
- Tabela comparativa entre projetos.
- Curva S consolidada (normalizada em % para permitir somar cronogramas com unidades diferentes), com indicador visual do término de cada projeto.
- Exportação de relatório (Excel e PDF) da visão de portfólio.

### Exportação
- Relatório geral (Excel/PDF) e Relatório Executivo por período (PDF com Curva S, Gantt e lista de atividades filtrados).
- Relatórios exportados sempre em português, independente do idioma da interface.

### Idioma
- Alternância Português/Inglês na barra lateral, incluindo formatação de datas (dd/mm/aaaa em português, mm/dd/aaaa em inglês).

## Como rodar localmente

Requer Python 3.10+.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Ou, no Windows, basta executar `Iniciar Dashboard.bat`.

Para habilitar upload de `.mpp` (opcional): instale o Java e descomente as linhas `mpxj` e `JPype1` em `requirements.txt`.

## Testes

A suíte de testes cobre leitura de XML, indicadores EVM, Curva S, portfólio, checklist, relatórios Excel/PDF e a interface (via `streamlit.testing.v1.AppTest`, sem navegador):

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Estrutura do projeto

```
app.py                     Interface Streamlit (abas, widgets, orquestração)
cronograma/
  modelos.py                Dataclasses (Projeto, Tarefa, Recurso, Dependência)
  leitor_xml.py              Leitor de arquivos .xml (MSPDI)
  leitor_mpp.py               Leitor opcional de .mpp via MPXJ/Java
  metricas.py                Cálculo de indicadores EVM e percepções
  curva_s.py                  Geração da Curva S
  checklist.py                Checklist de qualidade do cronograma
  portfolio.py                Consolidação de múltiplos projetos
  relatorios.py                Exportação Excel/PDF (individual e portfólio)
  i18n.py                      Traduções PT/EN e formatação de datas
tests/                       Suíte de testes (pytest + AppTest)
requirements.txt
requirements-dev.txt         Dependências extras para desenvolvimento/testes
Iniciar Dashboard.bat        Atalho para rodar no Windows
```

## Publicação

O app pode ser publicado gratuitamente no [Streamlit Community Cloud](https://share.streamlit.io), gerando um link público. Dados enviados pelos usuários não são armazenados permanentemente — só o código-fonte fica no repositório.
