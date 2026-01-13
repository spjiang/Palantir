from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: str
    label: str = "Concept"
    name: str
    props: dict[str, Any] = Field(default_factory=dict)


class Relation(BaseModel):
    id: str
    type: str = "RELATED_TO"
    src: str
    dst: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    nodes: List[Entity]
    edges: List[Relation]


class ImportResult(BaseModel):
    created_nodes: int
    created_edges: int
    sample_nodes: List[Entity] = Field(default_factory=list)
    sample_edges: List[Relation] = Field(default_factory=list)


class EntityCreate(BaseModel):
    name: str
    label: str = "Concept"
    props: dict[str, Any] = Field(default_factory=dict)


class RelationCreate(BaseModel):
    type: str = "RELATED_TO"
    src: str
    dst: str
    props: dict[str, Any] = Field(default_factory=dict)


class GraphQuery(BaseModel):
    root_id: Optional[str] = None
    depth: int = 1
