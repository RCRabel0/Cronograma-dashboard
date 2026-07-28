from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Dependencia:
    predecessora_uid: str
    tipo: int = 1  # 0=Término-Término, 1=Término-Início, 2=Início-Término, 3=Início-Início


@dataclass
class Tarefa:
    uid: str
    id: int
    nome: str
    nivel_esquema: int = 0
    resumo: bool = False
    marco: bool = False
    critica: bool = False
    percentual_concluido: float = 0.0

    inicio: Optional[date] = None
    termino: Optional[date] = None
    inicio_linha_base: Optional[date] = None
    termino_linha_base: Optional[date] = None
    inicio_real: Optional[date] = None
    termino_real: Optional[date] = None

    duracao_horas: float = 0.0
    duracao_linha_base_horas: float = 0.0
    duracao_real_horas: float = 0.0

    custo: float = 0.0
    custo_linha_base: float = 0.0
    custo_real: float = 0.0

    manual: bool = False
    tipo_restricao: int = 0  # MSPDI ConstraintType: 0=ASAP, 1=ALAP, 2=MSO, 3=MFO, 4=SNET, 5=SNLT, 6=FNET, 7=FNLT
    folga_horas: Optional[float] = None
    wbs: str = ""

    recursos: list[str] = field(default_factory=list)
    dependencias: list["Dependencia"] = field(default_factory=list)

    @property
    def atrasada(self) -> bool:
        if self.percentual_concluido >= 100:
            return False
        if self.termino_linha_base is None or self.termino is None:
            return False
        return self.termino > self.termino_linha_base


@dataclass
class Recurso:
    uid: str
    nome: str
    trabalho_horas: float = 0.0
    custo: float = 0.0


@dataclass
class Projeto:
    nome: str
    inicio: Optional[date] = None
    termino: Optional[date] = None
    data_status: Optional[date] = None
    numero_baselines_salvas: int = 0
    data_salva_linha_base: Optional[date] = None
    tarefas: list[Tarefa] = field(default_factory=list)
    recursos: list[Recurso] = field(default_factory=list)

    @property
    def tarefas_detalhe(self) -> list[Tarefa]:
        """Tarefas que não são linhas de resumo (grupos) nem marcos."""
        return [t for t in self.tarefas if not t.resumo]

    @property
    def tem_custo(self) -> bool:
        """Indica se o arquivo tem custos reais preenchidos (recursos com tarifa/custo)."""
        return any((t.custo_linha_base or t.custo) for t in self.tarefas_detalhe)

    @property
    def tarefa_resumo_projeto(self) -> Optional[Tarefa]:
        """Tarefa de resumo raiz do projeto (nível 0), a mesma linha que o MS Project usa
        para exibir o % Concluído geral no topo do cronograma."""
        candidatas = [t for t in self.tarefas if t.nivel_esquema == 0]
        return candidatas[0] if candidatas else None
