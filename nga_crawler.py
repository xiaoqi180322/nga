import requests
import json
import time
from datetime import datetime
import os

# 配置项（从环境变量读取，避免硬编码）
NGA_URL = "https://nga.178.com/thread.php?searchpost=1&authorid=150058"
SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
# 请求头（模拟浏览器，避免被反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": os.getenv("NGA_COOKIE"),  # 从环境变量获取Cookie
    "Referer": "https://nga.178.com/"
}

def fetch_nga_posts():
    """抓取NGA用户回复帖子"""
    try:
        # 发送请求（设置超时，避免卡死）
        response = requests.get(NGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()  # 抛出HTTP错误（如403/500）
        response.encoding = "gbk"  # NGA页面编码为GBK，需指定
        
        # 简单解析（若需精准解析可使用BeautifulSoup，此处先返回页面长度+关键信息）
        # 测试阶段：返回页面长度和抓取时间，验证是否成功访问
        result = {
            "status": "success",
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "page_length": len(response.text),
            "message": "成功抓取NGA用户回复页面"
        }
        # 可选：若需解析具体帖子内容，可添加BeautifulSoup逻辑
        # from bs4 import BeautifulSoup
        # soup = BeautifulSoup(response.text, "html.parser")
        # posts = soup.find_all("div", class_="postcontent")  # 根据实际标签调整
        # result["posts_count"] = len(posts)
        
        return result
    
    except requests.exceptions.RequestException as e:
        # 捕获请求异常（网络错误、Cookie失效、403等）
        return {
            "status": "failed",
            "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e),
            "message": "抓取NGA页面失败"
        }

def push_to_serverchan(content):
    """推送消息到Server酱（微信）"""
    sendkey = os.getenv("SERVERCHAN_SENDKEY")
    if not sendkey:
        print("未配置Server酱SendKey，跳过推送")
        return False
    
    try:
        # 构造推送内容
        data = {
            "title": f"NGA抓取结果 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "desp": f"```json\n{json.dumps(content, ensure_ascii=False, indent=2)}\n```"  # 代码块格式展示
        }
        # 发送推送请求
        response = requests.post(SERVERCHAN_URL.format(sendkey=sendkey), data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            print("Server酱推送成功")
            return True
        else:
            print(f"Server酱推送失败：{result.get('message')}")
            return False
    except Exception as e:
        print(f"Server酱推送异常：{str(e)}")
        return False

def main():
    """主函数：抓取+推送"""
    print(f"开始执行抓取任务 - {datetime.now()}")
    # 1. 抓取NGA帖子
    fetch_result = fetch_nga_posts()
    print(f"抓取结果：{json.dumps(fetch_result, ensure_ascii=False)}")
    
    # 2. 推送结果到微信
    push_to_serverchan(fetch_result)
    
    # 3. 测试验证：若抓取失败，强制退出并返回错误码（GitHub Actions会识别）
    if fetch_result["status"] == "failed":
        exit(1)

if __name__ == "__main__":
    main()
