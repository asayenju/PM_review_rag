from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    org_id: str = Field(min_length=1)
    feature_id: str = Field(min_length=1)
    question: str = Field(min_length=3, max_length=1000)


class QueryResponse(BaseModel):
    answer: str


class PublicQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class AssignedFeatureResponse(BaseModel):
    org_id: str
    feature_id: str
    name: str
    slug: str | None = None


class CreateConversationRequest(BaseModel):
    org_id: str = Field(min_length=1)
    feature_id: str = Field(min_length=1)
    title: str | None = Field(default=None, max_length=200)


class ConversationResponse(BaseModel):
    id: str
    org_id: str
    feature_id: str | None = None
    feature_name: str | None = None
    title: str | None = None
    status: str
    updated_at: str | None = None


class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: str | None = None


class SendConversationMessageRequest(BaseModel):
    content: str = Field(min_length=3, max_length=1000)


class SendConversationMessageResponse(BaseModel):
    user_message: ConversationMessageResponse
    assistant_message: ConversationMessageResponse
