import logging
from typing import Optional

import httpx
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.media.dao import LinksDAO
from app.misc.faker import HEADERS

logger = logging.getLogger(__name__)


async def link_get(url, subreddit, session: AsyncSession = Depends(get_session)):
    existing_link = await LinksDAO.find_one_or_none(url=url, session=session)
    if existing_link:
        return existing_link
    else:
        return None


async def fetch_final_url(url: str) -> Optional[str]:
    """
    Следует перенаправлениям и получает конечный URL.
    """
    async with httpx.AsyncClient(follow_redirects=True, headers=HEADERS, timeout=10) as client:
        try:
            response = await client.head(url)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            logger.warning(f"HEAD request failed for {url}: {e}. Trying GET request.")
            try:
                response = await client.get(url)
                response.raise_for_status()
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                logger.error(f"GET request failed for {url}: {e}")
                return None
        logger.info(f"Final URL for {url} is {response.url}")
        return str(response.url)


# Дополнительная функция для загрузки файлов
async def download_file(url: str, file_path: str) -> bool:
    """
    Загружает файл по указанному URL и сохраняет его в заданном пути.

    Args:
        url (str): URL файла для загрузки.
        file_path (str): Локальный путь для сохранения загруженного файла.

    Returns:
        bool: True, если файл успешно загружен, иначе False.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return True
        except httpx.HTTPError as e:
            logger.error(f"Не удалось загрузить файл {url}: {e}")
            return False


async def get_file_size_mb(url: str) -> Optional[float]:
    """
    Get the size of the file in megabytes.

    Args:
        url (str): The URL of the file.

    Returns:
        Optional[float]: The size of the file in MB, or None if an error occurs.
    """
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            response = await client.head(url)
            response.raise_for_status()
            size_bytes = int(response.headers.get('Content-Length', 0))
            size_mb = round(size_bytes / (1024 * 1024), 1)
            return size_mb
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.error(f"Failed to get file size for {url}. Error: {e}")
            return None
