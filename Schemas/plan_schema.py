from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., max_length=50)
    monthly_price: int = Field(..., gt=0, le=10_000_000)
    annual_months_charged: int = Field(10, ge=1, le=24)

    @field_validator("name")
    @classmethod
    def plan_name(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("Enter a plan name.")
        return text


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(None, max_length=50)
    monthly_price: int | None = Field(None, gt=0, le=10_000_000)
    annual_months_charged: int | None = Field(None, ge=1, le=24)

    @field_validator("name")
    @classmethod
    def plan_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            raise ValueError("Enter a plan name.")
        return text
