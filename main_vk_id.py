import os
import uvicorn
import httpx
import secrets
import hashlib
import base64
import urllib.parse
from fastapi import FastAPI, Request, HTTPException
from starlette.responses import RedirectResponse
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

VK_CLIENT_ID = os.getenv("VK_ID_CLIENT_ID")
VK_CLIENT_SECRET = os.getenv("VK_ID_CLIENT_SECRET")
VK_REDIRECT_URI = os.getenv("VK_ID_REDIRECT_URI")

# Простая "fake DB", чтобы хранить session-данные
# В реальном приложении надо использовать Redis, DB и т.п.
fake_db = {}

def generate_code_verifier(length=50):
    """
    Генерируем code_verifier - строку длиной 43-128 символов.
    Можем использовать "secrets.token_urlsafe" и укоротить/удлинить.
    """
    verifier = secrets.token_urlsafe(length)
    return verifier

def generate_code_challenge(verifier):
    """
    Делаем SHA256 и кодируем в base64url (без = на конце)
    """
    sha256_hash = hashlib.sha256(verifier.encode('utf-8')).digest()
    challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8')
    # Срезаем "=", если они есть, чтоб было url-safe.
    challenge = challenge.replace('=', '')
    return challenge

@app.get("/")
def index():
    return {"message": "Отдельный сервер для OAuth2.1 авторизации через VK ID"}

@app.get("/vk/login")
def vk_login():
    if not VK_CLIENT_ID or not VK_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="VK_CLIENT_ID или VK_REDIRECT_URI не заданы")

    # Генерим "state" (CSRF защита)
    state = secrets.token_urlsafe(32)
    # Генерим PKCE
    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)

    # Сохраняем их в "fake_db" (ключом возьмём сам state).
    # В реальном проекте храните в session/Redis, или любым другим способом
    fake_db[state] = {
        "code_verifier": code_verifier,
        "used": False  # отметка, что ещё не использовался
    }

    params = {
        "response_type": "code",
        "client_id": VK_CLIENT_ID,
        "redirect_uri": VK_REDIRECT_URI,
        "scope": "openid phone email",   # Например, хотим phone и email
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # по желанию: "prompt": "consent" / "none" / "login"
    }

    url = f"https://id.vk.com/authorize?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)

@app.get("/vk/callback")
async def vk_callback(
    code: str = None,
    error: str = None,
    state: str = None,
    device_id: str = None
):
    """
    Эндпоинт, куда возвращается пользователь после
    авторизации на https://id.vk.com/.
    Получаем ?code=..., ?state=..., ?device_id=...
    """
    if error:
        raise HTTPException(status_code=400, detail=f"VK OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="VK не вернул code")
    if not state:
        raise HTTPException(status_code=400, detail="Отсутствует state")
    if state not in fake_db:
        raise HTTPException(status_code=400, detail="Неизвестный state")

    # Достаём из "сеанса"
    session_data = fake_db[state]
    if session_data["used"]:
        # Не даём использовать один и тот же state повторно
        raise HTTPException(status_code=400, detail="Этот state уже был использован")

    code_verifier = session_data["code_verifier"]
    # Помечаем, что больше нельзя использовать этот state повторно
    session_data["used"] = True

    # Собираем POST-запрос для обмена code -> токены
    token_url = "https://id.vk.com/oauth2/auth"
    data = {
        "grant_type": "authorization_code",
        "client_id": VK_CLIENT_ID,
        "code": code,
        "redirect_uri": VK_REDIRECT_URI,
        "code_verifier": code_verifier,
        "device_id": device_id if device_id else "",  # Можно подставить "" если не пришёл
        "state": state,
    }

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=data, headers=headers)
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"VK token error: {token_resp.text}")

        token_data = token_resp.json()

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=f"VK token error: {token_data}")

        # Тут у нас уже "правильные" токены
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        user_id = token_data["user_id"]

        # Если хотим получить данные о пользователе (немаскированные):
        userinfo_url = "https://id.vk.com/oauth2/user_info"
        userinfo_data = {
            "client_id": VK_CLIENT_ID,
            "access_token": access_token,
        }
        userinfo_headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        profile_resp = await client.post(userinfo_url, data=userinfo_data, headers=userinfo_headers)
        profile_data = profile_resp.json()

        return {
            "oauth_tokens": token_data,
            "profile_data": profile_data
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
