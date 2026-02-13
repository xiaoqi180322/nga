import requests
import json
import time
from datetime import datetime, timedelta
import os
from bs4 import BeautifulSoup
import re
import pytz

# ===== 配置区 =====
NGA_URL = "https://nga.178.com/thread.php?searchpost=1&authorid=150058"
SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
HISTORY_FILE = "nga_post_history.json"
DAYS_TO_KEEP = 3  # 仅保留最近3天的回复

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": os.getenv("NGA_COOKIE"),
    "Referer": "https://nga.178.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

# ===== 北京时间工具函数 =====
def get_beijing_time():
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz)

def beijing_time_str(fmt="%Y-%m-%d %H:%M:%S"):
    return get_beijing_time().strftime(fmt)

# ===== 测试函数 =====
def test_nga_connection():
    print("\n[测试1] 测试NGA连接与Cookie有效性...")
    try:
        response = requests.get(NGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = "gbk"
        page_length = len(response.text)
        if "登录" in response.text[:2000] or "请先登录" in response.text[:2000]:
            print("❌ NGA连接成功，但Cookie无效或已过期，页面被重定向到登录页")
            return False
        else:
            print(f"✅ NGA连接成功，页面长度: {page_length}，Cookie有效")
            return True
    except requests.exceptions.RequestException as e:
        print(f"❌ NGA连接失败: {str(e)}")
        return False

def test_history_file():
    print("\n[测试2] 测试历史文件读写...")
    test_data = {
        "test_post": "test_content",
        "timestamp": beijing_time_str()
    }
    try:
        with open("test_history.tmp", "w", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False, indent=2)
        with open("test_history.tmp", "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
        if loaded_data == test_data:
            print("✅ 历史文件读写测试通过")
            os.remove("test_history.tmp")
            return True
        else:
            print("❌ 历史文件读写测试失败：数据不一致")
            return False
    except Exception as e:
        print(f"❌ 历史文件读写测试失败: {str(e)}")
        return False

def test_serverchan_push():
    print("\n[测试3] 测试Server酱推送...")
    sendkey = os.getenv("SERVERCHAN_SENDKEY")
    if not sendkey:
        print("❌ 未配置Server酱SendKey，跳过推送测试")
        return False
    try:
        test_title = "NGA工作流测试推送（北京时间）"
        test_desp = f"测试时间: {beijing_time_str()}\n这是一条来自GitHub Actions的测试消息"
        data = {"title": test_title, "desp": test_desp}
        response = requests.post(SERVERCHAN_URL.format(sendkey=sendkey), data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            print("✅ Server酱推送测试成功，微信/APP应收到测试消息")
            return True
        else:
            print(f"❌ Server酱推送测试失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Server酱推送测试异常: {str(e)}")
        return False

# ===== 核心功能 =====
def parse_nga_time(nga_time_str):
    try:
        return datetime.strptime(nga_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            return datetime.strptime(nga_time_str, "%Y-%m-%d")
        except:
            return get_beijing_time() - timedelta(days=DAYS_TO_KEEP + 1)

def is_within_3_days(post_time):
    three_days_ago = get_beijing_time() - timedelta(days=DAYS_TO_KEEP)
    return post_time >= three_days_ago

def load_and_clean_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            filtered_posts = []
            for post in history["posts"]:
                post_time = parse_nga_time(post["post_time"])
                if is_within_3_days(post_time):
                    filtered_posts.append(post)
            history["posts"] = filtered_posts
            history["last_clean_time"] = beijing_time_str()
            save_history(history)
            return history
        except Exception as e:
            print(f"加载/清理历史记录失败: {e}")
            return {"posts": [], "last_update": "", "last_clean_time": ""}
    else:
        init_data = {
            "posts": [],
            "last_update": beijing_time_str(),
            "last_clean_time": beijing_time_str()
        }
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(init_data, f, ensure_ascii=False, indent=2)
        return init_data

def save_history(history_data):
    history_data["last_update"] = beijing_time_str()
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存历史记录失败: {e}")
        return False

def parse_nga_posts(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    valid_posts = []
    post_items = soup.find_all("div", class_="postrow")

    for item in post_items:
        try:
            post_id = item.get("id", "")
            if not post_id:
                continue

            time_elem = item.find("div", class_="postdate")
            post_time_str = time_elem.get_text(strip=True) if time_elem else ""
            if not post_time_str:
                continue
            post_time = parse_nga_time(post_time_str)
            if not is_within_3_days(post_time):
                continue

            thread_elem = item.find("a", href=re.compile(r"thread\.php\?tid="))
            thread_title = thread_elem.get_text(strip=True) if thread_elem else "未知标题"
            thread_url = "https://nga.178.com/" + thread_elem["href"] if thread_elem else ""

            # ===== 抓取完整回复内容（不再截断）=====
            content_elem = item.find("div", class_="postcontent")
            if content_elem:
                # 移除图片标签，保留纯文本
                for img in content_elem.find_all("img"):
                    img.decompose()
                post_content = content_elem.get_text(strip=True, separator="\n")
            else:
                post_content = "无内容"

            post_info = {
                "post_id": post_id,
                "post_time": post_time_str,
                "thread_title": thread_title,
                "thread_url": thread_url,
                "post_content": post_content,  # 完整内容
                "crawl_time": beijing_time_str()
            }
            valid_posts.append(post_info)
        except Exception as e:
            print(f"解析单条回复失败: {e}")
            continue

    return valid_posts

def fetch_nga_posts():
    try:
        response = requests.get(NGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = "gbk"
        valid_posts = parse_nga_posts(response.text)
        history = load_and_clean_history()
        history_post_ids = [p["post_id"] for p in history["posts"]]
        new_posts = [p for p in valid_posts if p["post_id"] not in history_post_ids]

        if new_posts:
            history["posts"].extend(new_posts)
            history["posts"] = list({p["post_id"]: p for p in history["posts"]}.values())
            save_history(history)

        return {
            "status": "success",
            "valid_posts_count": len(valid_posts),
            "new_posts_count": len(new_posts),
            "new_posts": new_posts
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "new_posts_count": 0,
            "new_posts": []
        }

def format_posts_for_push(new_posts):
    if not new_posts:
        return "暂无3天内的新回复"

    push_content = ""
    for i, post in enumerate(new_posts, 1):
        push_content += f"""
### 新回复 {i}
- 发布时间：{post['post_time']}
- 原帖：[{post['thread_title']}]({post['thread_url']})
- 完整内容：
{post['post_content']}
        """
    return push_content.strip()

def push_to_serverchan(new_posts):
    sendkey = os.getenv("SERVERCHAN_SENDKEY")
    if not sendkey:
        print("未配置Server酱SendKey，跳过推送")
        return False

    title = f"NGA新回复提醒（近3天） {beijing_time_str()}"
    desp = format_posts_for_push(new_posts)

    if desp == "暂无3天内的新回复":
        print("无3天内的新回复，跳过推送")
        return True

    try:
        data = {"title": title, "desp": desp}
        response = requests.post(SERVERCHAN_URL.format(sendkey=sendkey), data=data, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            print("✅ Server酱推送成功（微信/APP已收到）")
            return True
        else:
            print(f"❌ Server酱推送失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ Server酱推送异常: {str(e)}")
        return False

# ===== 主函数 =====
def main():
    print(f"===== 开始执行NGA抓取任务 {beijing_time_str()} =====")

    print("\n===== 前置测试 =====")
    test_passed = True
    if not test_nga_connection():
        test_passed = False
    if not test_history_file():
        test_passed = False
    if not test_serverchan_push():
        test_passed = False

    if test_passed:
        print("\n✅ 所有测试通过，开始抓取...")
    else:
        print("\n⚠️ 部分测试失败，继续执行...")

    crawl_result = fetch_nga_posts()
    if crawl_result["status"] == "success":
        print(f"\n本次抓取到 {crawl_result['valid_posts_count']} 条3天内的回复（含历史）")
        if crawl_result["new_posts_count"] > 0:
            print(f"发现 {crawl_result['new_posts_count']} 条新回复，正在推送...")
            push_to_serverchan(crawl_result["new_posts"])
        else:
            print("无新回复，跳过推送")
    else:
        print(f"\n❌ 抓取失败: {crawl_result.get('error', '未知错误')}")
        push_to_serverchan([{
            "post_content": f"抓取失败：{crawl_result.get('error', '未知错误')}",
            "post_time": beijing_time_str("%Y-%m-%d %H:%M"),
            "thread_title": "抓取异常提醒",
            "thread_url": NGA_URL
        }])

    print(f"\n===== 任务执行完成 {beijing_time_str()} =====")

if __name__ == "__main__":
    main()
