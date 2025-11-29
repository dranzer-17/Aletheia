from fastapi import APIRouter, Form, Request
from fastapi.responses import Response
from typing import Optional
import logging
import html
import os
from .whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter()

# Try to import Twilio (optional for active messaging)
try:
    from twilio.rest import Client
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        USE_ACTIVE_MESSAGING = True
        logger.info("✅ Twilio Client initialized - using ACTIVE messaging")
    else:
        twilio_client = None
        USE_ACTIVE_MESSAGING = False
        logger.info("⚠️ Twilio credentials not found - using PASSIVE TwiML responses")
except ImportError:
    twilio_client = None
    USE_ACTIVE_MESSAGING = False
    logger.info("⚠️ Twilio SDK not installed - using PASSIVE TwiML responses")

@router.api_route("/webhook", methods=["GET", "POST"])
async def whatsapp_webhook_all(request: Request):
    """
    Catch-all webhook endpoint to debug what Twilio is sending
    """
    logger.info("="*80)
    logger.info(f"WEBHOOK HIT - Method: {request.method}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"URL: {request.url}")
    
    if request.method == "GET":
        query_params = dict(request.query_params)
        logger.info(f"GET Query Params: {query_params}")
        return {"status": "GET request received", "params": query_params}
    
    # Handle POST
    form_data = await request.form()
    form_dict = dict(form_data)
    logger.info(f"POST Form Data: {form_dict}")
    logger.info("="*80)
    
    return await whatsapp_webhook_post(
        Body=form_dict.get('Body'),
        MediaUrl0=form_dict.get('MediaUrl0'),
        From=form_dict.get('From'),
        To=form_dict.get('To')
    )

async def whatsapp_webhook_post(
    Body: Optional[str],
    MediaUrl0: Optional[str],
    From: Optional[str],
    To: Optional[str]
):
    """
    Process the WhatsApp webhook
    """
    try:
        logger.info("="*60)
        logger.info(f"WEBHOOK CALLED - From: {From}, Body: {Body}")
        logger.info("="*60)
        
        # Process the message using the service
        response_text = await WhatsAppService.process_message(
            body=Body,
            media_url=MediaUrl0,
            from_number=From
        )
        
        logger.info(f"Response text generated: {response_text[:100]}...")
        
        # Try ACTIVE messaging first (if Twilio SDK available)
        if USE_ACTIVE_MESSAGING and twilio_client and From:
            try:
                # Split long messages (WhatsApp limit is 1600 chars)
                max_length = 1500
                messages_to_send = [response_text[i:i+max_length] for i in range(0, len(response_text), max_length)]
                
                for msg_chunk in messages_to_send:
                    message = twilio_client.messages.create(
                        from_=TWILIO_WHATSAPP_NUMBER,
                        body=msg_chunk,
                        to=From
                    )
                    logger.info(f"✅ ACTIVE message sent via Twilio API - SID: {message.sid}")
                
                # Return empty TwiML (message already sent)
                return Response(
                    content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                    media_type="text/xml",
                    status_code=200
                )
            except Exception as twilio_error:
                logger.error(f"❌ Active messaging failed: {twilio_error}, falling back to TwiML")
        
        # Fallback to PASSIVE TwiML response
        # Escape XML special characters
        escaped_text = html.escape(response_text[:1500])  # Limit length
        
        # Format response in TwiML XML format required by Twilio
        twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>
        <Body>{escaped_text}</Body>
    </Message>
</Response>"""
        
        logger.info(f"Sending TwiML response (length: {len(twiml_response)})")
        return Response(content=twiml_response, media_type="text/xml", status_code=200)
        
    except Exception as e:
        logger.error(f"Unexpected error in webhook: {str(e)}", exc_info=True)
        
        # Send error message back to user
        error_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>
        <Body>❌ An unexpected error occurred. Please try again later.</Body>
    </Message>
</Response>"""
        
        return Response(content=error_twiml, media_type="text/xml", status_code=200)

@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy", "service": "whatsapp-misinformation-handler"}
