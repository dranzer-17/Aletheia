import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = 30

async def download_image(url: str, timeout: int = HTTP_TIMEOUT) -> bytes:
    """
    Download an image from a URL asynchronously
    """
    try:
        logger.info(f"Downloading image from: {url}")
        
        async with aiohttp.ClientSession() as session:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            
            async with session.get(url, timeout=timeout_obj) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download image. Status code: {response.status}")
                
                image_bytes = await response.read()
                
                logger.info(f"Successfully downloaded image ({len(image_bytes)} bytes)")
                return image_bytes
                
    except aiohttp.ClientError as e:
        logger.error(f"HTTP client error downloading image: {str(e)}")
        raise Exception(f"Failed to download image: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error downloading image: {str(e)}")
        raise
