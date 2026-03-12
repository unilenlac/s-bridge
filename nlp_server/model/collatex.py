from pydantic import BaseModel, Field
from typing import Optional 

class Token(BaseModel):
    text: str = Field(description="The original token text", serialization_alias="t")
    normalisation: str = Field(description="The normalisation of the text", serialization_alias="n")
    original: str = Field(default=None, description="The original token text", serialization_alias="o")
    lemma: str = Field(description="The lemma of the token", serialization_alias="lem")
    pos: Optional[str] = Field(default=None, description="The part of speech of the token", serialization_alias="pos")
    cs: Optional[str] = Field(default=None, description="The case of the token", serialization_alias="case")
    gender: Optional[str] = Field(default=None, description="The gender of the token", serialization_alias="gender")
    number: Optional[str] = Field(default=None, description="The number of the token", serialization_alias="number")
    
    # Editorial flags and metadata
    unclear: bool = Field(default=False, description="Whether the token is unclear", serialization_alias="unclear")
    unclear_reason: Optional[str] = Field(default=None, description="The reason the token is unclear", serialization_alias="unclear_reason")
    
    add: bool = Field(default=False, description="Whether the token is added", serialization_alias="add")
    add_hand: Optional[str] = Field(default=None, description="The hand of the added token", serialization_alias="add_hand")
    
    dl: bool = Field(default=False, description="Whether the token is deleted", alias="del", serialization_alias="del")
    del_reason: Optional[str] = Field(default=None, description="The reason the token is deleted", serialization_alias="del_reason")
    
    abbr: bool = Field(default=False, description="Whether the token is an abbreviation", serialization_alias="abbr")
    abbr_type: Optional[str] = Field(default=None, description="The type of abbreviation", serialization_alias="abbr_type")
    abbr_original: Optional[str] = Field(default=None, description="The original abbreviation text", serialization_alias="abbr_original")
    
    # ENLAC Semantic tags
    seg_type: Optional[str] = Field(default=None, description="The type of segment", serialization_alias="seg_type")
    seg_part: Optional[str] = Field(default=None, description="The part of the segment", serialization_alias="seg_part")
    
    note: bool = Field(default=False, description="Whether the token is a note", serialization_alias="note")
    note_type: Optional[str] = Field(default=None, description="The type of note", serialization_alias="note_type")
    
    head: bool = Field(default=False, description="Whether the token is a head", serialization_alias="head")

    subst: bool = Field(default=False, description="Wether the token is a substitution", serialization_alias="subst")