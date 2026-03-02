from pydantic import BaseModel, Field
from typing import Optional 

class Token(BaseModel):
    text: str = Field(description="The original token text", serialization_alias="t")
    lemma: str = Field(description="The lemma of the token", serialization_alias="n")
    original: Optional[str] = Field(description="The original token text", serialization_alias="o")
    pos: Optional[str] = Field(description="The part of speech of the token", serialization_alias="pos")
    cs: Optional[str] = Field(description="The case of the token", serialization_alias="case")
    gender: Optional[str] = Field(description="The gender of the token", serialization_alias="gender")
    number: Optional[str] = Field(description="The number of the token", serialization_alias="number")
    unclear: bool = Field(description="Whether the token is unclear", serialization_alias="unclear")
    unclear_reason: Optional[str] = Field(description="The reason the token is unclear", serialization_alias="unclear_reason")
    add: bool = Field(description="Whether the token is added", serialization_alias="add")
    add_hand: Optional[str] = Field(description="The hand of the added token", serialization_alias="add_hand")
    dl: Optional[str] = Field(description="The reason the token is deleted", serialization_alias="delete")
    abbr: bool = Field(description="Whether the token is an abbreviation", serialization_alias="abbr")
    abbr_type: Optional[str] = Field(description="The type of abbreviation", serialization_alias="abbr_type")
    abbr_original: Optional[str] = Field(description="The original abbreviation text", serialization_alias="abbr_original")
    seg_type: Optional[str] = Field(description="The type of segment", serialization_alias="seg_type")
    note: Optional[str] = Field(description="The note of the token", serialization_alias="note")
    head: Optional[str] = Field(description="The head of the token", serialization_alias="head")