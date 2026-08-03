from pydantic import BaseModel, HttpUrl
from datetime import datetime

class WebsiteCreate(BaseModel):
    url: HttpUrl

class WebsiteOut(BaseModel):
    id: int
    url: str
    created_at: datetime
    is_up: bool | None = None
    status_code: int | None =  None
    response_time_ms: float | None = None
    last_checked: datetime | None = None

    class config:
       from_attributes = True

class WebsiteDelete(BaseModel):
    url: HttpUrl

    class Config:
        from_attributes = True

class CheckOut(BaseModel):
   id: int
   website_id: int
   status_code: int | None
   response_time_ms: float | None
   is_up: bool
   checked_at: datetime

   class Config:
        from_attributes = True
