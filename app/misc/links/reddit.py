import asyncio
import logging
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, Optional, Tuple, List
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.media.dao import LinksDAO
from app.misc.faker import HEADERS
from app.misc.links.url_utils import download_file, fetch_final_url, get_file_size_mb
from app.schemas.files import RedditPostData

logger = logging.getLogger(__name__)

API_URL_REDGIFS = 'https://api.redgifs.com/v1/gifs/'
MEDIA_DIR = 'media_files'  # Directory for saving media files
os.makedirs(MEDIA_DIR, exist_ok=True)  # Create directory if it doesn't exist

MAX_VIDEO_SIZE_MB = 45  # Maximum allowed video size in MB


# Utility Functions

async def fetch_reddit_data(json_url: str) -> Optional[Dict]:
    """
    Fetch Reddit post data from the given JSON URL.

    Args:
        json_url (str): The URL to fetch the Reddit JSON data.

    Returns:
        Optional[Dict]: The JSON data as a dictionary, or None if an error occurs.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(json_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Reddit data. Error: {e}")
            return None


async def fetch_dash_xml(dash_url: str) -> Optional[str]:
    """
    Fetch the DASH XML file.

    Args:
        dash_url (str): The URL of the DASH XML file.

    Returns:
        Optional[str]: The DASH XML content as a string, or None if an error occurs.
    """
    async with httpx.AsyncClient(headers=HEADERS) as client:
        try:
            response = await client.get(dash_url)
            response.raise_for_status()
            return response.text
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch DASH XML. Error: {e}")
            return None


def find_dash_url(data: dict) -> Optional[str]:
    """
    Find the 'dash_url' in the Reddit post data.

    Args:
        data (dict): The Reddit post data.

    Returns:
        Optional[str]: The DASH URL if found, else None.
    """
    paths = [
        ("secure_media", "reddit_video", "dash_url"),
        ("crosspost_parent_list", 0, "secure_media", "reddit_video", "dash_url"),
    ]
    for path in paths:
        dash_url = data
        for key in path:
            if isinstance(dash_url, dict) and key in dash_url:
                dash_url = dash_url[key]
            elif isinstance(dash_url, list) and isinstance(key, int) and len(dash_url) > key:
                dash_url = dash_url[key]
            else:
                dash_url = None
                break
        if dash_url:
            return dash_url
    return None


def extract_redgifs_id(url: str) -> Optional[str]:
    """
    Extracts the GIF identifier from a redgifs.com URL.

    Args:
        url (str): The redgifs.com URL.

    Returns:
        Optional[str]: The GIF ID if extracted successfully, else None.
    """
    patterns = [
        r'redgifs\.com/watch/([\w-]+)',
        r'redgifs\.com/ifr/([\w-]+)',
        r'redgifs\.com/([\w-]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def get_redgifs_video_url(gif_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetches video information from redgifs.com API using the GIF identifier.

    Args:
        gif_id (str): The GIF identifier.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing video information, or None if an error occurs.
    """
    api_url = API_URL_REDGIFS + gif_id
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url)
            response.raise_for_status()
            redgifs_json = response.json()
            gfy_item = redgifs_json.get('gfyItem')
            if not gfy_item:
                logger.error("Failed to get 'gfyItem' from redgifs.com response.")
                return None
            return gfy_item
        except (httpx.HTTPError, KeyError, ValueError) as e:
            logger.error(f"Error fetching data from redgifs.com: {e}")
            return None


# Parsing Functions


async def get_video_info(resolution: str, video_url: str) -> Optional[Tuple[str, float, str]]:
    """
    Gets video resolution, size, and URL.

    Args:
        resolution (str): The video resolution (e.g., '720').
        video_url (str): The URL of the video.

    Returns:
        Optional[Tuple[str, float, str]]: A tuple containing resolution, size in MB, and video URL, or None if failed.
    """
    size_mb = await get_file_size_mb(video_url)
    if size_mb is not None:
        logger.debug(f"Video {resolution}p size: {size_mb} MB")
        return resolution, size_mb, video_url
    return None


async def extract_audio_link(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    """
    Extracts the audio link with the highest bandwidth from the DASH XML.

    Args:
        soup (BeautifulSoup): The parsed DASH XML.
        base_url (str): The base URL for constructing full URLs.

    Returns:
        Optional[str]: The audio URL if found, else None.
    """
    audio_adaptation_set = soup.find('AdaptationSet', {'contentType': 'audio'})
    if not audio_adaptation_set:
        return None

    highest_bandwidth = 0
    audio_base_url = None
    for representation in audio_adaptation_set.find_all('Representation'):
        bandwidth = int(representation.get('bandwidth', 0))
        if bandwidth > highest_bandwidth:
            highest_bandwidth = bandwidth
            base_url_elem = representation.find('BaseURL')
            if base_url_elem:
                audio_base_url = base_url_elem.text

    if audio_base_url:
        audio_url = base_url + audio_base_url
        logger.debug(f"Found audio URL: {audio_url}")
        return audio_url
    return None


async def extract_video_links(soup: BeautifulSoup, base_url: str) -> List[Dict[str, Any]]:
    """
    Extracts video links and their resolutions from the DASH XML.

    Args:
        soup (BeautifulSoup): The parsed DASH XML.
        base_url (str): The base URL for constructing full URLs.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing resolution, size in MB, and video URL.
    """
    video_links = []
    video_adaptation_set = soup.find('AdaptationSet', {'contentType': 'video'})
    if not video_adaptation_set:
        return video_links

    tasks = []
    representations = video_adaptation_set.find_all('Representation')

    for representation in representations:
        width = representation.get('width')
        base_url_elem = representation.find('BaseURL')
        if width and base_url_elem:
            video_url = base_url + base_url_elem.text
            tasks.append(get_video_info(width, video_url))

    video_info_list = await asyncio.gather(*tasks)

    for video_info in video_info_list:
        if video_info:
            resolution, size_mb, video_url = video_info
            if size_mb is not None and size_mb <= MAX_VIDEO_SIZE_MB:
                video_links.append({
                    'resolution': int(resolution),
                    'size_mb': size_mb,
                    'video_url': video_url
                })

    return video_links


async def parse_dash_xml(dash_url: str, base_url: str) -> Dict[str, Any]:
    """
    Parses DASH XML and returns video and audio URLs.

    Args:
        dash_url (str): The URL of the DASH XML file.
        base_url (str): The base URL for constructing full URLs.

    Returns:
        Dict[str, Any]: A dictionary containing 'audio' URL and list of 'videos'.
    """
    dash_xml = await fetch_dash_xml(dash_url)
    if not dash_xml:
        return {}

    soup = BeautifulSoup(dash_xml, 'xml')

    # Extract audio link
    audio_link = await extract_audio_link(soup, base_url)

    # Extract video links
    video_links = await extract_video_links(soup, base_url)

    logger.debug(f"Parsed video links: {video_links}")
    return {
        'audio': audio_link,
        'videos': video_links
    }


async def parse_dash_xml(dash_url: str, base_url: str) -> Dict[str, Any]:
    """
    Parses DASH XML and returns video and audio URLs.

    Args:
        dash_url (str): The URL of the DASH XML file.
        base_url (str): The base URL for constructing full URLs.

    Returns:
        Dict[str, Any]: A dictionary containing 'audio' URL and list of 'videos'.
    """
    dash_xml = await fetch_dash_xml(dash_url)
    if not dash_xml:
        return {}

    soup = BeautifulSoup(dash_xml, 'xml')

    # Extract audio link
    audio_link = await extract_audio_link(soup, base_url)

    # Extract video links
    video_links = await extract_video_links(soup, base_url)

    logger.debug(f"Parsed video links: {video_links}")
    return {
        'audio': audio_link,
        'videos': video_links
    }


# Post Processing Functions


async def process_redgifs_post(post_data: RedditPostData) -> dict:
    """
    Processes posts with redgifs.com links and returns relevant information.

    Args:
        post_data (RedditPostData): The Reddit post data.

    Returns:
        dict: A dictionary containing processed post information.
    """
    # Extract GIF ID from the URL
    redgifs_url = post_data.url
    gif_id = extract_redgifs_id(redgifs_url)
    if not gif_id:
        logger.error("Failed to extract GIF ID from redgifs.com URL.")
        return {}

    # Get video information
    gfy_item = await get_redgifs_video_url(gif_id)
    if not gfy_item:
        logger.error("Failed to get GIF information from redgifs.com.")
        return {}

    # Get available video URLs and sizes
    content_urls = gfy_item.get('content_urls', {})
    video_options = []

    for key in ['mp4', 'mobile', 'max5mbGif', 'max2mbGif']:
        video_info = content_urls.get(key)
        if video_info and 'url' in video_info and 'size' in video_info:
            size_mb = video_info['size'] / (1024 * 1024)
            if size_mb <= MAX_VIDEO_SIZE_MB:
                video_options.append(
                    {
                        'url': video_info['url'],
                        'size_mb': size_mb,
                        'width': video_info.get('width'),
                        'height': video_info.get('height'),
                        'key': key
                    })

    if not video_options:
        logger.error("No available video options within the allowed size limit.")
        return {}

    # Select the largest video within the size limit
    selected_video = max(video_options, key=lambda x: x['size_mb'])

    video_url = selected_video['url']
    video_size_mb = selected_video['size_mb']
    video_resolution = f"{selected_video.get('width')}x{selected_video.get('height')}"

    logger.info(f"Selected video: {video_url} ({video_size_mb:.2f} MB, {video_resolution})")

    # Create a temporary directory in the project folder
    temp_dir = tempfile.mkdtemp(dir=os.path.join(os.getcwd(), MEDIA_DIR))
    video_file_path = os.path.join(temp_dir, f"{gif_id}.mp4")

    # Download the video
    success = await download_file(video_url, video_file_path)
    if not success:
        logger.error(f"Error downloading video {video_url}")
        return {}

    redgifs_post_info = {
        'type': 'video',
        'title': post_data.title,
        'desc': post_data.selftext,
        'file_path': video_file_path,
        'temp_dir': temp_dir,
        'file_type': 'mp4',
        'over_18': post_data.over_18,
        'subreddit': post_data.subreddit,
        'permalink': f"https://www.reddit.com{post_data.permalink}",
    }
    logger.debug(f"Processed redgifs.com post: {redgifs_post_info}")
    return redgifs_post_info


async def process_image_post(post_data: RedditPostData) -> dict:
    """
    Processes image posts and returns relevant information.

    Args:
        post_data (RedditPostData): The Reddit post data.

    Returns:
        dict: A dictionary containing processed post information.
    """
    image_url = post_data.url
    if not image_url:
        logger.error("URL изображения отсутствует в данных поста.")
        return {}

    temp_dir = tempfile.mkdtemp(dir=os.path.join(os.getcwd(), MEDIA_DIR))

    # Проверяем, является ли изображение гифкой
    is_gif = image_url.endswith('.gif')

    if is_gif:
        # Попробуем найти mp4 версию в 'preview' данных
        preview = post_data.preview
        if preview:
            mp4_url = None
            if 'reddit_video_preview' in preview:
                mp4_url = preview['reddit_video_preview'].get('fallback_url')
            else:
                # Ищем mp4 в variants
                for image in preview.get('images', []):
                    variants = image.get('variants', {})
                    if 'mp4' in variants:
                        mp4_url = variants['mp4']['source']['url'].replace('&amp;', '&')
                        break
            if mp4_url:
                # Сохраняем mp4 файл
                file_extension = '.mp4'
                temp_file_path = os.path.join(temp_dir, f"image{file_extension}")
                success = await download_file(mp4_url, temp_file_path)
                if not success:
                    logger.error("Failed to download mp4 version of the image.")
                    return {}
            else:
                # Если mp4 версия недоступна, сохраняем как gif
                file_extension = '.gif'
                temp_file_path = os.path.join(temp_dir, f"image{file_extension}")
                success = await download_file(image_url, temp_file_path)
                if not success:
                    logger.error("Failed to download gif image.")
                    return {}
        else:
            # Если preview данных нет, сохраняем как gif
            file_extension = '.gif'
            temp_file_path = os.path.join(temp_dir, f"image{file_extension}")
            success = await download_file(image_url, temp_file_path)
            if not success:
                logger.error("Failed to download gif image.")
                return {}
    else:
        # Для не гифок
        parsed_url = urlparse(image_url)
        path = parsed_url.path
        file_extension = os.path.splitext(path)[1]
        if not file_extension:
            file_extension = '.jpg'

        temp_file_path = os.path.join(temp_dir, f"image{file_extension}")
        success = await download_file(image_url, temp_file_path)
        if not success:
            logger.error("Failed to download image.")
            return {}

    img_post_info = {
        'type': 'image',
        'title': post_data.title,
        'desc': post_data.selftext,
        'file_path': temp_file_path,
        'temp_dir': temp_dir,
        'file_type': file_extension[1:],
        'over_18': post_data.over_18,
        'subreddit': post_data.subreddit,
        'permalink': f"https://www.reddit.com{post_data.permalink}",
    }
    logger.debug(f"Processed image post: {img_post_info}")
    return img_post_info


async def process_video_post(post_data: RedditPostData) -> dict:
    """
    Processes video posts and returns relevant information.

    Args:
        post_data (RedditPostData): The Reddit post data.

    Returns:
        dict: A dictionary containing processed post information.
    """
    if not post_data.dash_url:
        logger.error("dash_url not found for video post.")
        return {}

    temp_dir = tempfile.mkdtemp(dir=os.path.join(os.getcwd(), MEDIA_DIR))

    # Parse DASH XML and get video and audio links
    media_dict = await parse_dash_xml(post_data.dash_url, post_data.url + '/')
    audio_link = media_dict.get('audio')
    video_options = media_dict.get('videos', [])

    if not video_options:
        logger.error("Failed to get video links.")
        return {}

    # Sort video options by resolution in descending order
    sorted_videos = sorted(video_options, key=lambda x: x['resolution'], reverse=True)

    # Select the highest resolution video within the size limit
    best_video = sorted_videos[0]
    video_url = best_video['video_url']
    video_resolution = best_video['resolution']
    video_size_mb = best_video['size_mb']

    logger.info(f"Selected video: {video_url} ({video_size_mb:.2f} MB, {video_resolution}p)")

    # Download video and audio files
    video_file_path = os.path.join(temp_dir, "video.mp4")
    audio_file_path = os.path.join(temp_dir, "audio.mp4")
    output_file_path = os.path.join(temp_dir, "output_video.mp4")

    download_tasks = [download_file(video_url, video_file_path)]
    if audio_link:
        download_tasks.append(download_file(audio_link, audio_file_path))

    results = await asyncio.gather(*download_tasks)

    if not all(results):
        logger.error("Error downloading video or audio files.")
        return {}

    # Merge video and audio using FFmpeg
    if audio_link:
        command = [
            'ffmpeg',
            '-i', video_file_path,
            '-i', audio_file_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-y', output_file_path
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            logger.info(f"Video and audio successfully merged into {output_file_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error merging video and audio: {e}")
            return {}
    else:
        output_file_path = video_file_path

    video_post_info = {
        'type': 'video',
        'title': post_data.title,
        'desc': post_data.selftext,
        'file_path': output_file_path,
        'temp_dir': temp_dir,
        'file_type': 'mp4',
        'over_18': post_data.over_18,
        'subreddit': post_data.subreddit,
        'permalink': post_data.permalink,
    }
    logger.debug(f"Processed video post: {video_post_info}")
    return video_post_info


async def process_gallery_post(post_data: RedditPostData) -> dict:
    """
    Processes gallery posts and returns relevant information.

    Args:
        post_data (RedditPostData): The Reddit post data.

    Returns:
        dict: A dictionary containing processed post information.
    """
    media_metadata = post_data.media_metadata
    if not media_metadata:
        logger.error("media_metadata not found for gallery.")
        return {}

    temp_dir = tempfile.mkdtemp(dir=os.path.join(os.getcwd(), MEDIA_DIR))
    files = []

    # Get list of media_ids in order from gallery_data
    media_items = post_data.gallery_data['items']
    media_ids = [item['media_id'] for item in media_items]

    async def download_media(idx, media_id):
        media_info = media_metadata.get(media_id)
        if not media_info:
            logger.warning(f"No information for media_id {media_id}")
            return None

        media_type = media_info.get('e')
        if media_type not in ['Image', 'AnimatedImage']:
            logger.warning(f"Unknown media type {media_type} for media_id {media_id}")
            return None

        if media_type == 'Image':
            source = media_info.get('s')
            if not source:
                logger.warning(f"No source for image media_id {media_id}")
                return None

            image_url = source['u'].replace('&amp;', '&')
            parsed_url = urlparse(image_url)
            path = parsed_url.path
            file_extension = os.path.splitext(path)[1]
            if not file_extension:
                file_extension = '.jpg'

            temp_file_path = os.path.join(temp_dir, f"media_{idx}{file_extension}")

            success = await download_file(image_url, temp_file_path)
            if not success:
                logger.error(f"Failed to download image {image_url}")
                return None
            return temp_file_path

        elif media_type == 'AnimatedImage':
            source = media_info.get('s')
            if not source:
                logger.warning(f"No source for animated image media_id {media_id}")
                return None

            mp4_url = source.get('mp4')
            gif_url = source.get('gif')

            if mp4_url:
                media_url = mp4_url.replace('&amp;', '&')
                file_extension = '.mp4'
            elif gif_url:
                media_url = gif_url.replace('&amp;', '&')
                file_extension = '.gif'
            else:
                logger.warning(f"No available URLs for animated image media_id {media_id}")
                return None

            temp_file_path = os.path.join(temp_dir, f"media_{idx}{file_extension}")

            success = await download_file(media_url, temp_file_path)
            if not success:
                logger.error(f"Failed to download media {media_url}")
                return None
            return temp_file_path

        return None  # Should not reach here

    download_tasks = []
    for idx, media_id in enumerate(media_ids):
        download_tasks.append(download_media(idx, media_id))

    files = await asyncio.gather(*download_tasks)
    files = [f for f in files if f is not None]  # Filter successful downloads

    gallery_post_info = {
        'type': 'gallery',
        'title': post_data.title,
        'desc': post_data.selftext,
        'file_paths': files,
        'temp_dir': temp_dir,
        'over_18': post_data.over_18,
        'subreddit': post_data.subreddit,
        'permalink': f"https://www.reddit.com{post_data.permalink}",
    }
    logger.debug(f"Processed gallery post: {gallery_post_info}")
    return gallery_post_info


def process_other_post(post_data: RedditPostData) -> dict:
    """
    Processes other types of posts and returns relevant information.

    Args:
        post_data (RedditPostData): The Reddit post data.

    Returns:
        dict: The post data as a dictionary.
    """
    logger.info(f"Processing other post type: {post_data}")
    return post_data.dict()


async def fetch_reddit_json_data(json_data: Dict) -> Optional[dict]:
    """
    Processes Reddit JSON data and extracts relevant information.

    Args:
        json_data (Dict): The Reddit JSON data.

    Returns:
        Optional[dict]: A dictionary containing processed post information, or None if an error occurs.
    """
    try:
        post_data_dict = json_data[0]['data']['children'][0]['data']
    except (IndexError, KeyError) as e:
        logger.error(f"Invalid Reddit JSON structure: {e}")
        return None

    # Check if the post was removed
    if post_data_dict.get('removed_by_category') == 'deleted':
        logger.error("Post was deleted by the author or moderators.")
        return {
            'status': 'error',
            'message': 'The post was deleted by the author or moderators.'
        }

    dash_url = find_dash_url(post_data_dict)
    if dash_url:
        post_data_dict['dash_url'] = dash_url

    try:
        post_data = RedditPostData.parse_obj(post_data_dict)
    except ValidationError as e:
        logger.error(f"Pydantic validation error: {e}")
        return None

    if post_data.domain in ['redgifs.com', 'www.redgifs.com']:
        return await process_redgifs_post(post_data)
    elif post_data.is_gallery:
        return await process_gallery_post(post_data)
    elif post_data.is_video:
        return await process_video_post(post_data)
    elif post_data.post_hint == "image":
        return await process_image_post(post_data)
    else:
        return process_other_post(post_data)


async def match_reddit(url: str, session: AsyncSession) -> Optional[dict]:
    """
    Processes a Reddit URL and returns relevant post data.
    If the post data is already in the database, returns it directly.

    Args:
        url (str): The Reddit URL.
        session (AsyncSession): The database session.

    Returns:
        Optional[dict]: A dictionary containing processed post information, or None if an error occurs.
    """
    short_url_pattern = r'https?://www\.reddit\.com/r/[^\s]+/s/[^\s]+'
    standard_url_pattern = r'(?:https?://)?(?:www\.)?reddit\.com/(r|user)/([^/]+)/comments/([^/]+)'

    # Check if URL is a short form and expand it if necessary
    if re.match(short_url_pattern, url):
        final_url = await fetch_final_url(url)
        match = re.search(standard_url_pattern, final_url)
    else:
        match = re.search(standard_url_pattern, url)

    if match:
        subreddit = match.group(2)
        post_id = match.group(3)
        json_url = f'https://www.reddit.com/r/{subreddit}/comments/{post_id}.json'

        # Check if the link is already in the database
        existing_link = await LinksDAO.find_one_or_none(session, url=json_url)
        if existing_link:
            logger.info(f"Link already exists in the database: {json_url}")
            return existing_link

        # Fetch Reddit data
        post_data = await fetch_reddit_data(json_url)
        if not post_data:
            logger.error("Failed to fetch data from Reddit.")
            return None

        # Process Reddit JSON data
        post_parsed_data = await fetch_reddit_json_data(post_data)
        if not post_parsed_data:
            logger.error("Failed to process Reddit JSON data.")
            return None

        if post_parsed_data.get('status') == 'error':
            # Return error message
            return post_parsed_data

        # Save link info to the database if needed
        # await save_link_info_to_db(post_parsed_data, session)

        return post_parsed_data

    else:
        logger.error("Invalid Reddit URL format.")
        return None
