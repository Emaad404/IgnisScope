from typing import Literal

from pydantic import BaseModel, Field

Provenance = Literal["SOURCE_SUPPORTED", "USER_ASSUMED", "UNKNOWN"]


class InvestigationIn(BaseModel):
    psi_id: str | None = Field(None, max_length=40)
    title: str = Field(min_length=3, max_length=300)
    description: str | None = None
    source_url: str | None = Field(None, max_length=500)
    nasa_verified: bool = False
    is_synthetic: bool = False
    gravity_context: str | None = Field(None, max_length=120)
    gravity_provenance: Provenance = "UNKNOWN"


class TargetCondition(BaseModel):
    variable: Literal["oxygen_fraction", "pressure", "flow_velocity", "temperature",
                      "thickness", "width", "gravity"]
    value: float
    unit: str = Field(min_length=1, max_length=30)
    tolerance_pct: float = Field(10.0, gt=0, le=100)


class EnvironmentIn(BaseModel):
    name: Literal["ISS", "LUNAR_HABITAT", "MARS_TRANSIT", "CUSTOM"] | None = None
    provenance: Provenance = "USER_ASSUMED"   # selecting an environment never fills physical values


class StructuredQuery(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    phenomenon: Literal["flame_spread"] = "flame_spread"
    material: str | None = Field(None, max_length=100)
    required_measurements: list[str] = []
    target_conditions: list[TargetCondition] = []
    environment: EnvironmentIn = EnvironmentIn()
    include_synthetic: bool = True


class ParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
