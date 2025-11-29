import logging
from typing import Optional
from .detector_client import analyze_text, analyze_image
from .utils import download_image

logger = logging.getLogger(__name__)

class WhatsAppService:
    @staticmethod
    async def process_message(
        body: Optional[str] = None,
        media_url: Optional[str] = None,
        from_number: Optional[str] = None
    ) -> str:
        """
        Process incoming WhatsApp message and return response
        """
        try:
            response_text = ""
            
            if media_url:
                logger.info("Processing image...")
                try:
                    image_bytes = await download_image(media_url)
                    context = body if body else "Analyze this image for misinformation."
                    analysis_result = await analyze_image(image_bytes, context)
                    response_text = f"🔍 *Image Analysis Result:*\n\n{analysis_result}"
                except Exception as e:
                    logger.error(f"Error processing image: {str(e)}")
                    response_text = f"❌ Sorry, I couldn't analyze the image. Error: {str(e)}"
            
            elif body:
                logger.info("Processing text...")
                try:
                    analysis_result = await analyze_text(body)
                    response_text = f"🔍 *Analysis Result:*\n\n{analysis_result}"
                except Exception as e:
                    logger.error(f"Error processing text: {str(e)}")
                    response_text = f"❌ Sorry, I couldn't analyze the text. Error: {str(e)}"
            
            else:
                response_text = "👋 Hi! Send me a message or image to check for misinformation.\n\n📝 Text: I'll analyze claims and statements\n🖼️ Image: I'll analyze visual content"
            
            return response_text
        
        except Exception as e:
            logger.error(f"Unexpected error in process_message: {str(e)}")
            return "❌ An unexpected error occurred. Please try again later."
