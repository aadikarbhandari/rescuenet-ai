#!/usr/bin/env python3

import json
import requests
from pathlib import Path

API_KEY = "FRP2SDJ5SFQ2J2JDKJBAXLJNEFO2NNBRDOVA"
BASE_URL = "https://api.vultrinference.com/v1"
MODEL = "GLM-5-FP8"

FILE = Path("/root/rescuenet-ai/dashboard/app.py")

def call_glm(code):
    prompt = f"""
Fix this Streamlit app.

Problem:
App runs but shows blank/black page.

Fix so:
- always renders UI
- no crashes if data missing
- shows title + visible content
- uses fallback dummy data

Return ONLY raw Python code.

CODE:
{code}
"""

    print("→ Calling GLM API...")

    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "max_tokens": 6000,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=60   # ← IMPORTANT (prevents hanging)
    )

    print("→ Response received")

    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"]

    # remove ``` if present
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])

    return text.strip()


def main():
    if not FILE.exists():
        print("app.py not found")
        return

    print("Reading app.py...")
    code = FILE.read_text()

    fixed = call_glm(code)

    print("Writing fixed file...")
    FILE.write_text(fixed)

    print("\nDONE. Now run:")
    print("cd /root/rescuenet-ai/dashboard")
    print("streamlit run app.py --server.port 8501")


if __name__ == "__main__":
    main()
