# -*- coding: utf-8 -*-
import base64, json, os, struct, zlib, urllib.error, urllib.request

# 入口：base_url / api_key 从环境变量读
BASE = os.getenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
KEY = os.environ["LLM_API_KEY"]


def call(path, body, timeout=120):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:300]}


def chat(prompt, model=None):
    body = {
        "model": model or os.getenv("LLM_MODEL", "qwen-vl-max"),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
    }
    data = call("/chat/completions", body)
    if "_error" in data:
        raise RuntimeError(f"{data['_error']} {data['_body']}")
    return data["choices"][0]["message"]["content"].strip()


def vision(image_bytes, prompt):
    b64 = base64.b64encode(image_bytes).decode()
    body = {
        "model": os.getenv("VISION_MODEL", "qwen-vl-max"),
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": 300,
    }
    data = call("/chat/completions", body)
    if "_error" in data:
        raise RuntimeError(f"{data['_error']} {data['_body']}")
    return data["choices"][0]["message"]["content"].strip()


def _png(w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))

    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


if __name__ == "__main__":
    print(chat("用一句话说明什么是 RAG。"))
    print(vision(_png(64, 64, (30, 80, 200)), "这张图是什么颜色？只回答颜色。"))
