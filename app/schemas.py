from pydantic import BaseModel, Field


class Column(BaseModel):
    name: str
    type: str = "text"
    primary_key: bool = False
    nullable: bool = True


class Entity(BaseModel):
    name: str
    columns: list[Column]


class Relation(BaseModel):
    name: str = Field(default="", description="label written on the relationship diamond")
    from_entity: str
    to_entity: str
    kind: str = Field(description="one-to-one | one-to-many | many-to-many")


class ParsedDiagram(BaseModel):
    entities: list[Entity]
    relations: list[Relation] = []
    notes: str = Field(default="", description="anything unclear or illegible")