from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from datetime import datetime

class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str

class WebsiteCreate(BaseModel):
    url: HttpUrl

class WebsiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    url: str
    created_at: datetime
    is_up: bool | None = None
    status_code: int | None = None
    response_time_ms: float | None = None
    last_checked: datetime | None = None
    ai_summary: str | None = None

class WebsiteDelete(BaseModel):
    url: HttpUrl

class CheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    website_id: int
    status_code: int | None
    response_time_ms: float | None
    is_up: bool
    error: str | None = None
    checked_at: datetime
    ai_summary: str | None = None

class AnalysisOut(BaseModel):
    website_id: int
    url: str
    error: str | None = None
    title: str | None = None
    page_size_bytes: int = 0
    word_count: int = 0
    link_count: int = 0
    image_count: int = 0
    images_missing_alt: int = 0
    script_count: int = 0
    has_meta_description: bool = False
    top_words: list[tuple[str, int]] = []

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)

class AskSource(BaseModel):
    check_id: int
    url: str
    checked_at: datetime
    is_up: bool
    status_code: int | None

class AskResponse(BaseModel):
    answer: str
    sources: list[AskSource]
