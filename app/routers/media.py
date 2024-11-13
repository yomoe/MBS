import logging
import os
import shutil
from typing import Callable, Dict, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.media.dao import LinksDAO
from app.misc.links.reddit import match_reddit
from app.schemas.files import GetMedia
from app.schemas.users import UserInfo

logger = logging.getLogger(__name__)
router_media = APIRouter(
    prefix="/api/v1/media",
    tags=["media"],
)

# Словарь с источниками и их обработчиками
source_handlers: Dict[str, Callable[[str], Optional[Dict[str, str]]]] = {
    'reddit': match_reddit,
    # 'instagram': match_instagram,
}


def get_source_handler(url: str) -> Optional[Callable[[str], Optional[Dict[str, str]]]]:
    if 'reddit.com' in url:
        return source_handlers['reddit']
    # elif 'instagram.com' in url:
    #     return source_handlers['instagram']
    return None


@router_media.post('/combine')
async def get_media(link_request: GetMedia, session: AsyncSession = Depends(get_session)):
    url = link_request.url
    data = await match_reddit(url, session)
    if data:
        if data.get('status') == 'error':
            return {"status": "error", "message": data.get('message')}
        else:
            return {"status": "success", "data": data}
    else:
        return {"status": "error", "message": "Не удалось обработать ссылку Reddit."}
