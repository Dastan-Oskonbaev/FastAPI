import os
import httpx
import secrets

import urllib.parse
from fastapi import FastAPI, , HTTPException
from starlette.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

YANDEX_CLIENT_ID = os.getenv("YANDEX_CLIENT_ID")
YANDEX_CLIENT_SECRET = os.getenv("YANDEX_CLIENT_SECRET")
YANDEX_REDIRECT_URI = os.getenv("YANDEX_REDIRECT_URI")

fake_db = {}

@app.get("/ya/login")
def ya_login():
    state = secrets.token_urlsafe(32)
    fake_db[state] = {"used": False}

    params = {
        "response_type": "code",
        "client_id": YANDEX_CLIENT_ID,
        "redirect_uri": YANDEX_REDIRECT_URI,
        "scope": "login:email login:info",
        "state": state,
    }
    url = f"https://oauth.yandex.ru/authorize?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)


@app.get("/ya/callback")
async def ya_callback(code: str = None, state: str = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Code или state отсутствует")
    if state not in fake_db or fake_db[state]["used"]:
        raise HTTPException(status_code=400, detail="Неверный или использованный state")
    fake_db[state]["used"] = True

    token_url = "https://oauth.yandex.ru/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": YANDEX_CLIENT_ID,
        "client_secret": YANDEX_CLIENT_SECRET,
        "redirect_uri": YANDEX_REDIRECT_URI
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=data)
        token_data = token_resp.json()

        access_token = token_data["access_token"]
        user_info_resp = await client.get(
            "https://login.yandex.ru/info?format=json",
            headers={"Authorization": f"OAuth {access_token}"}
        )
        user_info = user_info_resp.json()

        return {
            "oauth_tokens": token_data,
            "profile_data": user_info
        }
