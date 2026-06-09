from pydantic import BaseModel


class ColumnSemanticResponse(BaseModel):

    column_id: int

    business_name: str | None = None

    business_description: str | None = None

    prompt_id: str | None = None

    prompt_version: str | None = None

    model_name: str | None = None

    column_category: str | None = None

    is_pii: bool = False

    pii_type: str | None = None

    risk_level: str | None = None

    confidence_score: float = 0.0

    class Config:
        from_attributes = True
