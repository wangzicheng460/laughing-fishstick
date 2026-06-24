@echo off
title AI 解析服务器 - 诊断学 & 听诊学习系统
echo =============================================
echo  🚀 正在启动 AI 解析服务器...
echo =============================================
echo.
echo  如果第一次使用，请先配置 API 密钥：
echo  1. 打开 https://platform.deepseek.com/api_keys
echo  2. 注册并创建 API Key
echo  3. 将密钥粘贴到 api_key.txt
echo  4. 诊断学系统：http://localhost:5001/app
echo  5. 听诊系统： http://localhost:5001/tingzhen
echo.
echo =============================================
echo.

python "%~dp0ai_server.py"

echo.
pause
