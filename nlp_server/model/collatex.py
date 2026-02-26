from pydantic import BaseModel, Field

class Token(BaseModel):
    text: str = Field(description="The original token text", serialization_alias="t")
    lemma: str = Field(description="The lemma of the token", serialization_alias="n")