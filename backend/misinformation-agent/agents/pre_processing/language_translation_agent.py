from typing import Tuple
from deep_translator import GoogleTranslator
import sys
from pathlib import Path

# Add backend root to path for logger import
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
from logger import get_logger

logger = get_logger(__name__)
SEPARATOR = "-" * 100

def run(claim_text: str) -> Tuple[str, str, str]:
    """
    Detects the language of the claim and translates it to English using
    the free and reliable deep_translator library.
    """
    logger.info(SEPARATOR)
    logger.info("--- LANGUAGE TRANSLATION AGENT BEING CALLED ---")
    
    try:
        # The library handles detection automatically with source='auto'
        # and translates to english with target='en'
        translated_text = GoogleTranslator(source='auto', target='en').translate(claim_text)
        
        # Check if translation was necessary
        if translated_text.lower() != claim_text.lower():
            # To get the detected language, we can re-translate a small part to detect
            # This is a small quirk of the library's simplicity
            detected_language = GoogleTranslator().detect(claim_text)[0]
            logger.info(f"Detected language: '{detected_language}'. Translated to: '{translated_text}'")
        else:
            detected_language = 'en'
            logger.info("Claim is already in English. No translation needed.")

        logger.info("--- LANGUAGE TRANSLATION AGENT FINISHED ---")
        logger.info(SEPARATOR)
        return detected_language, translated_text, claim_text

    except Exception as e:
        logger.error("An error occurred during translation. Defaulting to original text.", exc_info=True)
        logger.info("--- LANGUAGE TRANSLATION AGENT FINISHED (with error) ---")
        logger.info(SEPARATOR)
        return 'en', claim_text, claim_text