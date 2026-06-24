#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 解析服务器 - 为诊断学习系统提供 AI 自动解析

用法：
  1. 获取 API 密钥（二选一）:
     a) DeepSeek: https://platform.deepseek.com/api_keys  注册送 500 万 tokens
     b) 豆包 (火山引擎): https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint

  2. 将密钥填入下面的 API_KEY 或创建 api_key.txt

  3. 运行: python ai_server.py

  4. 双击打开 诊断学试题集_学习系统.html，点击 🤖 AI解析 即可
"""
import json
import http.server
import urllib.request
import urllib.error
import sys
import os
import re

# ===== 配置区 =====

# 🔑 在这里填入你的 API 密钥（二选一）
# DeepSeek: https://platform.deepseek.com/api_keys
API_KEY = ""

# 如果 API_KEY 为空，程序会从下面的文件读取
API_KEY_FILE = "api_key.txt"

# 选择 AI 后端: "deepseek" 或 "doubao" 或 "ollama"
AI_BACKEND = "deepseek"

# ---- DeepSeek 配置 ----
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

# ---- 豆包 (火山引擎) 配置 ----
# 从 https://console.volcengine.com/ark/region:ark+cn-beijing/endpoint 获取
DOUBAO_MODEL = "doubao-1-5-pro-32k-250515"
DOUBAO_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
# 豆包 API 密钥也在火山引擎控制台获取

# ---- Ollama 本地配置（备选） ----
OLLAMA_MODEL = "qwen2.5"
OLLAMA_URL = "http://localhost:11434/api/generate"

# =================================


def load_api_key():
    """从文件加载 API 密钥"""
    global API_KEY
    if API_KEY:
        return True
    # 尝试从 api_key.txt 读取
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), API_KEY_FILE)
    if os.path.exists(key_file):
        with open(key_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    API_KEY = line
                    return True
    return False


def build_prompt(question, options_list, answer, user_answer=None):
    """构建解析用的 prompt"""
    opts = "\n".join(options_list)
    parts = [
        "你是一个医学诊断学考试辅导老师。请详细解析以下题目，要求：",
        "1. 逐一分析每个选项，解释为什么对或为什么错",
        "2. 指出该题考察的核心知识点",
        "3. 给出通俗易懂的记忆方法或解题技巧",
        "4. 用中文回答，保持专业但易懂",
        "",
        f"【题目】{question}",
        "",
        "【选项】",
        opts,
        "",
        f"【正确答案】{answer}",
    ]
    if user_answer:
        parts.append(f"【用户选的答案】{user_answer}")
        parts.append("请指出用户做错（或做对）的原因，以及如何避免类似错误。")
    parts.append("")
    parts.append("请给出解析：")
    return "\n".join(parts)


def call_deepseek(prompt):
    """调用 DeepSeek API"""
    data = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "你是一名医学诊断学考试辅导专家，擅长解析医学选择题。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"].strip()


def call_doubao(prompt):
    """调用豆包 API（火山引擎）"""
    data = json.dumps({
        "model": DOUBAO_MODEL,
        "messages": [
            {"role": "system", "content": "你是一名医学诊断学考试辅导专家，擅长解析医学选择题。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000
    }).encode("utf-8")

    req = urllib.request.Request(
        DOUBAO_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        },
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode("utf-8"))
    return result["choices"][0]["message"]["content"].strip()


def call_ollama(prompt):
    """调用本地 Ollama"""
    data = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3}
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    result = json.loads(resp.read().decode("utf-8"))
    return result.get("response", "").strip()


def call_ai(prompt):
    """调用配置的 AI 后端"""
    if AI_BACKEND == "ollama":
        return call_ollama(prompt)
    elif AI_BACKEND == "doubao":
        return call_doubao(prompt)
    else:
        return call_deepseek(prompt)


class Handler(http.server.BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    def do_OPTIONS(self):
        self._cors_headers()
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            has_key = load_api_key() or AI_BACKEND == "ollama"
            status = "ok" if has_key else "no_key"
            self.wfile.write(
                f"AI 解析服务器运行中\n"
                f"状态: {'已就绪' if has_key else '未配置密钥'}\n"
                f"后端: {AI_BACKEND}\n"
                f"访问网页: http://localhost:{port}/app"
                .encode("utf-8")
            )
        elif self.path == "/status":
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            has_key = load_api_key() or AI_BACKEND == "ollama"
            self.wfile.write(json.dumps({
                "status": "ok" if has_key else "no_key",
                "backend": AI_BACKEND,
                "key_configured": has_key,
                "message": "运行正常" if has_key else "请配置 API 密钥（见 ai_server.py 或 api_key.txt）"
            }, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/app":
            """服务 HTML 页面，避免 file:// 跨域问题"""
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "诊断学试题集_学习系统.html")
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.wfile.write("<h1>HTML 文件不存在</h1>".encode("utf-8"))
        elif self.path == "/tingzhen":
            """服务听诊学习系统 HTML 页面"""
            self.send_response(200)
            self._cors_headers()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "听诊学习系统.html")
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.wfile.write(content.encode("utf-8"))
            else:
                self.wfile.write("<h1>HTML 文件不存在</h1>".encode("utf-8"))
        elif self.path == "/tingzhen_data.json":
            """服务听诊题目数据 JSON"""
            self._serve_json_file("tingzhen_data.json")
        elif self.path == "/exam_data.json":
            """服务诊断学题目数据 JSON"""
            self._serve_json_file("exam_data.json")
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_json_file(self, filename):
        """Helper to serve a JSON file with CORS headers."""
        self.send_response(200)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        fpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if os.path.exists(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
        else:
            self.wfile.write("{}".encode("utf-8"))

    def do_POST(self):
        if self.path == "/explain":
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                self._json_response({"error": "请求体为空"}, 400)
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                self._json_response({"error": "JSON 格式错误"}, 400)
                return

            question = body.get("question", "")
            options = body.get("options", [])
            answer = body.get("answer", "")
            user_answer = body.get("userAnswer", "")

            if not question:
                self._json_response({"error": "缺少题目内容"}, 400)
                return

            # 检查 API 密钥
            if AI_BACKEND != "ollama" and not load_api_key():
                self._json_response({
                    "success": False,
                    "explanation": (
                        "⚠️ 请先配置 API 密钥\n\n"
                        "方法一：编辑 ai_server.py，在 API_KEY 处填入密钥\n"
                        "方法二：在项目目录创建 api_key.txt，将密钥粘贴进去\n\n"
                        "🔑 获取密钥：https://platform.deepseek.com/api_keys\n"
                        "（注册即送 500 万 tokens，足够用很久）"
                    ),
                    "need_key": True
                })
                return

            prompt = build_prompt(question, options, answer, user_answer)

            try:
                explanation = call_ai(prompt)
                self._json_response({
                    "success": True,
                    "explanation": explanation,
                    "backend": AI_BACKEND
                })
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                self._json_response({
                    "success": False,
                    "explanation": f"❌ API 请求失败 (HTTP {e.code})\n\n{err_body[:500]}"
                })
            except urllib.error.URLError as e:
                self._json_response({
                    "success": False,
                    "explanation": f"❌ 网络连接失败：{e.reason}\n\n请检查网络连接和 API 地址配置。"
                })
            except Exception as e:
                self._json_response({
                    "success": False,
                    "explanation": f"❌ 解析失败：{str(e)[:300]}"
                })

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json_response(self, data, status=200):
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        sys.stderr.write(f"[AI解析] {args[0]} {args[1]} {args[2]}\n")


if __name__ == "__main__":
    # 设置控制台编码为 UTF-8，解决 Windows 中文显示问题
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    port = 5001

    print("=" * 50)
    print("AI 解析服务器")
    print("=" * 50)

    if AI_BACKEND == "ollama":
        print(f"后端：Ollama (本地) / {OLLAMA_MODEL}")
        print("使用前请确保已安装 Ollama 并已拉取模型")
    else:
        has_key = load_api_key()
        backend_name = "DeepSeek" if AI_BACKEND == "deepseek" else "豆包(火山引擎)"
        print(f"后端：{backend_name}")
        if has_key:
            print(f"API 密钥：已配置")
        else:
            print(f"API 密钥：未配置")
            print(f"请编辑 ai_server.py 填入 API_KEY")
            print(f"或创建 api_key.txt 放入密钥")
            print(f"获取密钥：https://platform.deepseek.com/api_keys")
            print(f"（注册即送 500 万 tokens）")

    print(f"地址：http://localhost:{port}")
    print(f"访问网页：http://localhost:{port}/app")
    print(f"听诊系统：http://localhost:{port}/tingzhen")
    print(f"或双击 HTML 文件也可（AI解析需通过上方地址打开）")
    print("=" * 50)

    server = http.server.HTTPServer(("localhost", port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务器已关闭")
        server.server_close()
