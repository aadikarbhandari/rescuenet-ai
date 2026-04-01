#!/usr/bin/env python3
"""
Fix all Python files in rescuenet-ai using GLM.
Removes XML junk, fixes syntax errors, preserves logic.
"""

import os
import requests

API_KEY = os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("API_KEY")
BASE_URL = "https://api.siliconflow.cn/v1"
GLM_MODEL = "THUDM/glm-4-9b-chat"  # update if your model name differs

FILES_TO_FIX = [
    "/root/rescuenet-ai/agents/triage.py",
    "/root/rescuenet-ai/agents/coordinator.py",
    "/root/rescuenet-ai/agents/perception.py",
    "/root/rescuenet-ai/agents/state_awareness.py",
    "/root/rescuenet-ai/agents/voice.py",
    "/root/rescuenet-ai/agents/routing.py",
    "/root/rescuenet-ai/agents/security.py",
    "/root/rescuenet-ai/config/settings.py",
    "/root/rescuenet-ai/simulation/mock_env.py",
    "/root/rescuenet-ai/dashboard/app.py",
    "/root/rescuenet-ai/main.py",
]

def call_glm(content: str) -> str:
    prompt = f"""You are a Python code fixer. The file below may contain:
- Stray XML tags like </parameter>, </drone_id>, </ etc. at the end or middle of the file
- Syntax errors caused by these tags
- Incomplete functions

Your job:
1. Remove ALL XML/HTML tags that don't belong in Python code
2. Fix any syntax errors
3. If a function is cut off, close it properly with `pass` or a return statement
4. Return the COMPLETE fixed Python file and nothing else
5. No markdown fences, no explanation, just the raw Python code

FILE TO FIX:
{content}"""

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": GLM_MODEL,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=120
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()

def fix_file(path: str):
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return

    with open(path, "r") as f:
        original = f.read()

    # Quick check — does it have XML junk?
    has_xml = "</" in original or "<parameter" in original
    
    # Also check for syntax errors
    import ast
    has_syntax_error = False
    try:
        ast.parse(original)
    except SyntaxError as e:
        has_syntax_error = True
        print(f"  Syntax error at line {e.lineno}: {e.msg}")

    if not has_xml and not has_syntax_error:
        print(f"  OK (no issues): {path}")
        return

    print(f"  Fixing: {path} (xml={has_xml}, syntax_error={has_syntax_error})")
    fixed = call_glm(original)

    # Strip markdown fences if GLM added them anyway
    if fixed.startswith("```"):
        lines = fixed.split("\n")
        fixed = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    # Verify it parses now
    try:
        ast.parse(fixed)
        with open(path, "w") as f:
            f.write(fixed)
        print(f"  FIXED: {path}")
    except SyntaxError as e:
        print(f"  GLM fix still has syntax error at line {e.lineno} — saving anyway, manual check needed")
        with open(path, "w") as f:
            f.write(fixed)

def main():
    if not API_KEY:
        print("ERROR: Set SILICONFLOW_API_KEY environment variable")
        return

    print("=== RescueNet File Fixer ===\n")
    for path in FILES_TO_FIX:
        fix_file(path)

    print("\n=== Done. Run: cd /root/rescuenet-ai && python main.py --mode demo --ticks 20 ===")

if __name__ == "__main__":
    main()
