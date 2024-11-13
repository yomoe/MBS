from typing import Any, Dict, Optional

from pydantic import BaseModel

from app.schemas.users import UserInfo


class FilesInfo(BaseModel):
    user_id: int
    url: str
    file_id: str
    file_type: str
    file_size: int


class GetMedia(UserInfo):
    url: str


class RedditPostData(BaseModel):
    title: str
    selftext: Optional[str] = ''
    url: str
    removed_by_category: Optional[str] = None
    post_hint: Optional[str] = None
    over_18: bool
    permalink: str
    is_video: bool
    dash_url: Optional[str] = None
    is_gallery: Optional[bool] = False
    domain: str
    subreddit: str
    image_url: Optional[str] = None
    media_metadata: Optional[Dict[str, Any]] = None
    gallery_data: Optional[Dict[str, Any]] = None
    preview: Optional[Dict[str, Any]] = None
