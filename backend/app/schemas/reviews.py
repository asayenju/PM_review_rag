from pydantic import BaseModel, Field


class CreateReviewRequest(BaseModel):
    org_id: str = Field(min_length=1)
    feature_id: str | None = None
    title: str | None = Field(default=None, max_length=300)
    body: str = Field(min_length=20)
    reviewer_name: str | None = Field(default=None, max_length=200)
    reviewer_email: str | None = Field(default=None, max_length=320)
    rating: int | None = Field(default=None, ge=1, le=10)


class RechunkResponse(BaseModel):
    review_id: str
    chunk_count: int
    status: str


class CreateReviewResponse(RechunkResponse):
    pass


class SeedDemoRequest(BaseModel):
    org_id: str = Field(min_length=1)
    feature_id: str | None = None


class SeedDemoResponse(BaseModel):
    review_id: str
    feature_id: str
    chunk_count: int
    status: str
    created: bool
