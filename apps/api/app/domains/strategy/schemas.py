"""Pydantic schemas for the SEO Strategy domain."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PersonaSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Persona name")
    description: str = Field(default="", description="Persona summary")
    problems: list[str] = Field(default_factory=list, description="Problems faced")
    goals: list[str] = Field(default_factory=list, description="Goals and objectives")
    funnel_stage: str = Field(default="TOFU", description="Target funnel stage")


class AudienceSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    segments: list[str] = Field(default_factory=list, description="Target segments")
    personas: list[PersonaSchema] = Field(default_factory=list, description="Target personas")
    needs: list[str] = Field(default_factory=list, description="Core customer needs")
    buying_stages: list[str] = Field(default_factory=list, description="Stages in buying journey")


class ProductServiceSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Product or service name")
    description: str = Field(default="", description="Short description")
    category: str = Field(default="service", description="product or service")
    url: str | None = Field(default=None, description="Landing page URL if known")
    priority: int = Field(default=1, description="Business priority (1 is highest)")


class MarketSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Market or country name")
    code: str = Field(default="", description="Country/region code")
    is_primary: bool = Field(default=False, description="Primary market")


class SEOGoalSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = Field(default="LEAD_GENERATION", description="Goal type")
    description: str = Field(default="", description="Goal details")
    priority: int = Field(default=1, description="Goal priority (1 is highest)")


class CompetitorSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", description="Competitor name")
    domain: str = Field(default="", description="Competitor domain")
    strengths: list[str] = Field(default_factory=list, description="Competitor strengths")


class BusinessContextSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    business_name: str = Field(default="", description="Business / brand name")
    description: str = Field(default="", description="Overview of business")
    industry: str = Field(default="", description="Primary industry")
    locations: list[str] = Field(default_factory=list, description="Physical/service locations")


class StrategyDataSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    business_context: BusinessContextSchema = Field(default_factory=BusinessContextSchema)
    audience: AudienceSchema = Field(default_factory=AudienceSchema)
    products: list[ProductServiceSchema] = Field(default_factory=list)
    services: list[ProductServiceSchema] = Field(default_factory=list)
    markets: list[MarketSchema] = Field(default_factory=list)
    goals: list[SEOGoalSchema] = Field(default_factory=list)
    competitors: list[CompetitorSchema] = Field(default_factory=list)
    seo_objectives: list[str] = Field(default_factory=list)
    content_objectives: list[str] = Field(default_factory=list)
    priority_topics: list[str] = Field(default_factory=list)


class StrategyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_data: StrategyDataSchema = Field(default_factory=StrategyDataSchema)
    change_summary: str = Field(default="Initial strategy creation")


class StrategyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_data: StrategyDataSchema
    change_summary: str = Field(default="Updated strategy")


class StrategyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    organization_id: UUID
    project_id: UUID
    current_version: int
    status: str
    strategy_data: StrategyDataSchema
    change_summary: str = ""
    created_at: datetime
    updated_at: datetime


class StrategyVersionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    strategy_id: UUID
    organization_id: UUID
    project_id: UUID
    version: int
    created_by_id: UUID | None = None
    change_summary: str
    strategy_data: StrategyDataSchema
    created_at: datetime


class StrategyVersionListResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[StrategyVersionResponse]
