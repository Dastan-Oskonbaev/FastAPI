import os
import uvicorn
import httpx
import urllib.parse

from fastapi import FastAPI, HTTPException
from starlette.responses import RedirectResponse
from dotenv import load_dotenv

# Загружаем переменные окружения из .env (если используете .env)
load_dotenv()

# Получаем данные клиента из Mail.ru
VK_CLIENT_ID = os.getenv("VK_ID_CLIENT_ID")
VK_CLIENT_SECRET = os.getenv("VK_ID_CLIENT_SECRET")
# Этот адрес должен быть прописан в настройках приложения Mail.ru
# и вести на эндпоинт ниже (/mailru/callback).
VK_REDIRECT_URI = os.getenv("VK_ID_REDIRECT_URI")

app = FastAPI()

@app.get("/")
def index():
    return {"message": "Отдельный сервер для авторизации через Mail.ru"}

@app.get("/vk/login")
async def vk_login():
    if not VK_CLIENT_ID or not VK_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="VK_CLIENT_ID или VK_REDIRECT_URI не заданы")

    params = {
        "response_type": "code",
        "client_id": VK_CLIENT_ID,
        "redirect_uri": VK_REDIRECT_URI,
        "scope": "openid profile email",
    }
    url = f"https://id.vk.com/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)



@app.get("/vk/callback")
async def vk_callback(code: str = None, error: str = None):
    if error:
        raise HTTPException(status_code=400, detail=f"VK OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="VK не вернул code")

    token_url = "https://api.vk.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": VK_CLIENT_ID,
        "client_secret": VK_CLIENT_SECRET,
        "redirect_uri": VK_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=data)
        token_data = token_resp.json()

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=f"VK token error: {token_data}")

        access_token = token_data["access_token"]
        user_id = token_data["user_id"]

        # получаем профиль
        userinfo_url = "https://api.vk.com/method/users.get"
        params = {
            "access_token": access_token,
            "user_ids": user_id,
            "fields": "first_name,last_name,photo_200,email",
            "v": "5.131"
        }
        profile_resp = await client.get(userinfo_url, params=params)
        profile_data = profile_resp.json()

        return profile_data




if __name__ == "__main__":
    # Запускаем этот "отдельный сервер"
    uvicorn.run(app, host="0.0.0.0", port=8001)
