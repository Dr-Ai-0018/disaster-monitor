"""
调试 RSOE API - 找到真正的事件列表端点
"""
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

# 尝试不同的 API 端点
endpoints = [
    "https://rsoe-edis.org/gateway/webapi/events/list",
    "https://rsoe-edis.org/gateway/webapi/events/all",
    "https://rsoe-edis.org/gateway/webapi/events",
    "https://rsoe-edis.org/api/events",
    "https://rsoe-edis.org/api/v1/events",
]

headers = settings.get_rsoe_headers()
cookies = settings.get_rsoe_cookies()

print("=" * 70)
print("尝试查找 RSOE 事件列表 API")
print("=" * 70)

for url in endpoints:
    print(f"\n尝试: {url}")
    try:
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=10)
        print(f"  状态码: {resp.status_code}")
        print(f"  Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        print(f"  响应长度: {len(resp.text)} 字符")
        
        if resp.status_code == 200:
            print(f"  ✅ 成功！")
            print(f"  前 200 字符: {resp.text[:200]}")
            
            # 尝试解析 JSON
            try:
                data = resp.json()
                print(f"  JSON 解析成功，键: {list(data.keys())[:10]}")
            except:
                print(f"  不是 JSON 格式")
        else:
            print(f"  ❌ 失败")
    except Exception as e:
        print(f"  ❌ 错误: {e}")

print("\n" + "=" * 70)
print("提示：请在浏览器中访问 https://rsoe-edis.org/eventList")
print("打开开发者工具 -> Network -> XHR，刷新页面")
print("找到获取事件列表的 API 请求，复制 URL")
print("=" * 70)
