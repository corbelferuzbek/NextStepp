"""NextStep backend bilan xavfsiz server-to-server aloqa."""
import httpx
from config import NEXTSTEP_API_URL, NEXTSTEP_API_KEY

TIMEOUT = httpx.Timeout(12.0, connect=5.0)

class NextStepError(Exception):
    pass

def configured():
    return bool(NEXTSTEP_API_URL and NEXTSTEP_API_KEY)

async def request(method, path, payload=None):
    if not configured():
        raise NextStepError("NextStep integratsiyasi sozlanmagan. Admin NEXTSTEP_API_URL va NEXTSTEP_API_KEY ni tekshirsin.")
    headers = {"X-API-Key": NEXTSTEP_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False) as client:
            response = await client.request(method, NEXTSTEP_API_URL + path, headers=headers, json=payload)
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400:
            code = data.get("error", "api_error") if isinstance(data, dict) else "api_error"
            messages = {
                "account_not_linked": "Hisobingiz hali bog'lanmagan. NextStep saytiga kiring va Profil bo'limida Telegram ID ni ulang.",
                "already_registered": "Siz bu musobaqaga avval ro'yxatdan o'tgansiz.",
                "contest_not_open": "Bu musobaqa hozir ro'yxatdan o'tish uchun ochiq emas.",
                "contest_not_found": "Musobaqa topilmadi.",
                "unauthorized": "NextStep API kaliti noto'g'ri. Admin sozlamalarni tekshirsin.",
            }
            raise NextStepError(messages.get(code, f"NextStep xatosi: {code}"))
        return data
    except httpx.TimeoutException as exc:
        raise NextStepError("NextStep serveri javob bermadi. Keyinroq urinib ko'ring.") from exc
    except httpx.HTTPError as exc:
        raise NextStepError("NextStep serveriga ulanib bo'lmadi.") from exc

async def contests():
    return await request("GET", "/api/integrations/telegram/contests")

async def wallet(telegram_id):
    return await request("GET", f"/api/integrations/telegram/wallet/{int(telegram_id)}")

async def history(telegram_id):
    data = await wallet(telegram_id)
    return data.get("transactions", [])

async def register(telegram_id, contest_id):
    return await request("POST", f"/api/integrations/telegram/contests/{int(contest_id)}/register", {"telegram_id": int(telegram_id)})
