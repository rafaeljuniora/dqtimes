# models.py (Atualizado)

import json
from datetime import datetime
from typing import List, Optional, Dict, Any


from sqlalchemy import JSON, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base

from pydantic import BaseModel, Field

# (Importações do SQLAlchemy e Base permanecem as mesmas)

# --- Definição dos Schemas de Resposta da API (Pydantic) ---

Base = declarative_base()

class Link(BaseModel):
    """ Estrutura para os hiperlinks de navegação (HATEOAS). """
    rel: str = Field(..., description="Relação do link (e.g., 'self', 'next', 'prev', 'first', 'last').")
    href: str = Field(..., description="URL completa para o recurso.")

class HistoryItemBase(BaseModel):
    """ Esquema base para um item de histórico, com datas padronizadas. """
    referencia: str = Field(..., description="ID de referência da execução (UUID).")
    task: str = Field(..., description="Nome da tarefa executada (e.g., 'naive_bayes').")
    status: str = Field(..., description="Status da execução (e.g., 'SUCCESS', 'ERROR').")
    
    # Padronização de datas para ISO 8601
    created_at: str = Field(..., description="Timestamp de criação (ISO 8601).")
    finished_at: Optional[str] = Field(None, description="Timestamp de finalização (ISO 8601).")

class HistoryItemExpanded(HistoryItemBase):
    """ Esquema para um item de histórico com detalhes expandidos. """
    # Nota: No campo 'details', a formatação de números deve ser feita no Python
    # antes de ser serializado para JSON, garantindo precisão e padrões.
    details: Optional[Dict[str, Any]] = Field(None, description="Detalhes completos da execução (parâmetros, resultados da previsão).")

class HistoryResponse(BaseModel):
    """ Esquema para a resposta completa com paginação e hiperlinks. """
    total_items: int = Field(..., description="Total de itens disponíveis, sem considerar a paginação.")
    page: int
    limit: int
    total_pages: int = Field(..., description="Número total de páginas disponíveis.")
    
    items: List[HistoryItemExpanded]
    
    # INCLUIR HIPERLINKS DE NAVEGAÇÃO
    links: List[Link]

class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, index=True)
    referencia = Column(String, unique=True, index=True)
    task = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime)
    finished_at = Column(DateTime, nullable=True)
    details = Column(JSON, nullable=True)