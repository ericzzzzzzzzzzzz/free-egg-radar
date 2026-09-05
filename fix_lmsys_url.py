#!/usr/bin/env python3
"""修复 lmsys.py 中的 URL（在 GitHub Actions 中运行）"""
import sys

with open('scrapers/lmsys.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'lmarena-ai/arena-leaderboard'
new = 'lmarena-ai/chatbot-arena-leaderboard'

if old in content:
    content = content.replace(old, new)
    with open('scrapers/lmsys.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('URL 已替换')
else:
    print('URL 已经是正确的，无需替换')

# 验证
with open('scrapers/lmsys.py', 'r', encoding='utf-8') as f:
    content = f.read()
if 'chatbot-arena-leaderboard' in content:
    print('验证通过：包含 chatbot-arena-leaderboard')
else:
    print('验证失败：不包含 chatbot-arena-leaderboard')
    sys.exit(1)
