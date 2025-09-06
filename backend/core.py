# /home/skillseek/app/backend/core.py
import base64, io, secrets, string
import qrcode

ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"  # без легко путаемых символов

def gen_lobby_code(length: int = 16) -> str:
    # читаемый код, lower-case
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

def make_qr_png_base64(payload: str) -> str:
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
