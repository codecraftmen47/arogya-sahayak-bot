from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import requests
from decouple import config
import logging
import httpx
from pydantic import BaseModel
from typing import Optional

# Configuration
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN')
TWILIO_NUMBER = config('TWILIO_WHATSAPP_NUMBER')  
RASA_WEBHOOK_URL = f"{config('RASA_SERVER_URL')}/webhooks/rest/webhook"
OPENAI_WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"

app = FastAPI(title="ArogyaSahayak Server")
'''app.mount("/static", StaticFiles(directory="static"), name="static")'''
templates = Jinja2Templates(directory="templates")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwilioWebhook(BaseModel):
    From: str
    To: str
    Body: Optional[str] = None
    NumMedia: Optional[str] = "0"
    MediaUrl0: Optional[str] = None

async def send_whatsapp_message(to: str, body: str):
    from twilio.rest import Client
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        from_=TWILIO_NUMBER,
        body=body,
        to=to
    )
    return message.sid

async def transcribe_voice_message(audio_url: str) -> str:
    async with httpx.AsyncClient() as client:
        audio_response = await client.get(audio_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        audio_data = audio_response.content

    files = {"file": ("voice-message.ogg", audio_data, "audio/ogg")}
    data = {"model": "whisper-1"}
    headers = {"Authorization": f"Bearer {config('OPENAI_API_KEY')}"}

    async with httpx.AsyncClient() as client:
        transcription_response = await client.post(OPENAI_WHISPER_URL, files=files, data=data, headers=headers)
        result = transcription_response.json()
        return result.get("text", "").strip()

@app.post("/webhook/twilio")
async def handle_twilio_webhook(request: Request):
    form_data = await request.form()
    twilio_data = TwilioWebhook(**form_data)

    user_phone = twilio_data.From
    user_message = twilio_data.Body
    logger.info(f"Received message from {user_phone}: {user_message}")

    if twilio_data.NumMedia != "0" and twilio_data.MediaUrl0:
        logger.info("Voice message detected. Transcribing...")
        user_message = await transcribe_voice_message(twilio_data.MediaUrl0)
        logger.info(f"Transcribed text: {user_message}")

    payload = {"sender": user_phone, "message": user_message}
    try:
        async with httpx.AsyncClient() as client:
            rasa_response = await client.post(RASA_WEBHOOK_URL, json=payload, timeout=30.0)
            rasa_response.raise_for_status()
            bot_replies = rasa_response.json()
    except httpx.RequestError as e:
        logger.error(f"Error communicating with Rasa: {e}")
        await send_whatsapp_message(user_phone, "Sorry, I'm having trouble right now. Please try again shortly.")
        return {"status": "error"}

    for reply in bot_replies:
        if 'text' in reply:
            await send_whatsapp_message(user_phone, reply['text'])

    return {"status": "success"}

@app.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    context = {"request": request, "active_users": 1500, "messages_today": 450}
    return templates.TemplateResponse("admin_dashboard.html", context)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)