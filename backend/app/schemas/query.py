from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    org_id: str = Field(min_length=1)
    feature_id: str = Field(min_length=1)
    question: str = Field(min_length=3, max_length=1000)


class QueryResponse(BaseModel):
    answer: str


class PublicQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
