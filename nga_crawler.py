import requests
import json
import time
from datetime import datetime, timedelta
import os
from bs4 import BeautifulSoup
import re

# 配置项
NGA_URL = "https://nga.178.com/thread.php?searchpost=1&authorid=150058"
SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
HISTORY_FILE = "nga_post_history.json"  # 存储历史回复的JSON文件
DAYS_TO_KEEP = 3  # 仅保留最近3天的回复
# 请求头（增强模拟浏览器，避免反爬）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": os.getenv("NGA_COOKIE"),
    "Referer": "https://nga.178.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

def parse_nga_time(nga_time_str):
    """解析NGA回复时间字符串为datetime对象（适配NGA时间格式：2026-02-14 10:00）"""
    try:
        # NGA回复时间格式示例：2026-2-14 15:30 或 2026-02-14 9:05
        return datetime.strptime(nga_time_str, "%Y-%m-%d %H:%M")
    except ValueError:
        try:
            # 兼容其他可能的格式（如仅日期）
            return datetime.strptime(nga_time_str, "%Y-%m-%d")
        except:
            # 解析失败返回当前时间（会被过滤掉）
            return datetime.now() - timedelta(days=DAYS_TO_KEEP + 1)

def is_within_3_days(post_time):
    """判断回复时间是否在最近3天内"""
    three_days_ago = datetime.now() - timedelta(days=DAYS_TO_KEEP)
    return post_time >= three_days_ago

def load_and_clean_history():
    """加载历史记录并清理超过3天的回复"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            
            # 清理超过3天的回复
            filtered_posts = []
            for post in history["posts"]:
                post_time = parse_nga_time(post["post_time"])
                if is_within_3_days(post_time):
                    filtered_posts.append(post)
            
            # 更新历史记录（仅保留3天内的）
            history["posts"] = filtered_posts
            history["last_clean_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_history(history)
            print(f"历史记录清理完成，保留 {len(filtered_posts)} 条3天内的回复")
            return history
        except Exception as e:
            print(f"加载/清理历史记录失败，初始化空记录：{e}")
            return {"posts": [], "last_update": "", "last_clean_time": ""}
    else:
        # 初始化历史文件结构
        init_data = {
            "posts": [], 
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_clean_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(init_data, f, ensure_ascii=False, indent=2)
        return init_data

def save_history(history_data):
    """保存更新后的历史记录"""
    history_data["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        print("历史记录保存成功")
        return True
    except Exception as e:
        print(f"保存历史记录失败：{e}")
        return False

def parse_nga_posts(html_content):
    """解析NGA页面，提取用户最近3天的回复核心信息"""
    soup = BeautifulSoup(html_content, "html.parser")
    valid_posts = []  # 仅存储3天内的回复
    
    # NGA回复列表的核心标签
    post_items = soup.find_all("div", class_="postrow")
    for item in post_items:
        try:
            # 提取回复ID（唯一标识）
            post_id = item.get("id", "")
            if not post_id:
                continue
            
            # 提取并解析回复时间
            time_elem = item.find("div", class_="postdate")
            post_time_str = time_elem.get_text(strip=True) if time_elem else ""
            if not post_time_str:
                continue
            post_time = parse_nga_time(post_time_str)
            
            # 过滤超过3天的回复
            if not is_within_3_days(post_time):
                continue
            
            # 提取回复对应的帖子标题和链接
            thread_elem = item.find("a", href=re.compile(r"thread\.php\?tid="))
            thread_title = thread_elem.get_text(strip=True) if thread_elem else "未知标题"
            thread_url = "https://nga.178.com/" + thread_elem["href"] if thread_elem else ""
            
            # 提取回复内容（清理多余标签）
            content_elem = item.find("div", class_="postcontent")
            if content_elem:
                # 移除图片、广告等无关标签
                for img in content_elem.find_all("img"):
                    img.decompose()
                post_content = content_elem.get_text(strip=True, separator="\n")[:500]  # 截断过长内容
            else:
                post_content = "无内容"
            
            # 构造回复信息字典
            post_info = {
                "post_id": post_id,
                "post_time": post_time_str,  # 保留原始时间字符串
                "thread_title": thread_title,
                "thread_url": thread_url,
                "post_content": post_content,
                "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            valid_posts.append(post_info)
        except Exception as e:
            print(f"解析单条回复失败：{e}")
            continue
    
    print(f"本次抓取到 {len(valid_posts)} 条3天内的回复（含历史）")
    return valid_posts

def fetch_nga_posts():
    """抓取并解析NGA用户最近3天的回复，返回新增回复"""
    try:
        response = requests.get(NGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = "gbk"  # NGA强制GBK编码
        
        # 解析3天内的回复
        valid_posts = parse_nga_posts(response.text)
        
        # 加载并清理历史记录
        history = load_and_clean_history()
        history_post_ids = [p["post_id"] for p in history["posts"]]
        
        # 筛选新增回复（3天内+未记录）
        new_posts = [p for p in valid_posts if p["post_id"] not in history_post_ids]
        
        # 更新历史记录（仅添加3天内的新回复）
        if new_posts:
            history["posts"].extend(new_posts)
            # 去重（防止重复抓取）
            history["posts"] = list({p["post_id"]: p for p in history["posts"]}.values())
            save_history(history)
            print(f"发现 {len(new_posts)} 条3天内的新回复，已更新历史记录")
        else:
            print("无3天内的新回复")
        
        return {
            "status": "success",
            "valid_posts_count": len(valid_posts),
            "new_posts_count": len(new_posts),
            "new_posts": new_posts,
            "message": "抓取并解析成功"
        }
    
    except requests.exceptions.RequestException as e:
        return {
            "status": "failed",
            "error": str(e),
            "new_posts_count": 0,
            "new_posts": [],
            "message": "抓取失败"
        }

def format_posts_for_push(new_posts):
    """格式化新回复，用于Server酱推送"""
    if not new_posts:
        return "暂无3天内的新回复"
    
    push_content = ""
    for i, post in enumerate(new_posts, 1):
        push_content += f"""
### 新回复 {i}
- 发布时间：{post['post_time']}
- 帖子：[{post['thread_title']}]({post['thread_url']})
- 内容：{post['post_content']}
        """
    return push_content.strip()

def push_to_serverchan(new_posts):
    """推送3天内的新回复到Server酱（微信+APP）"""
    sendkey = os.getenv("SERVERCHAN_SENDKEY")
    if not sendkey:
        print("未配置Server酱SendKey，跳过推送")
        return False
    
    # 构造推送标题和内容
    title = f"NGA新回复提醒（近3天） {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    desp = format_posts_for_push(new_posts)
    
    # 无新回复时不推送
    if desp == "暂无3天内的新回复":
        print("无3天内的新回复，跳过推送")
        return True
    
    try:
        data = {"title": title, "desp": desp}
        response = requests.post(SERVERCHAN_URL.format(sendkey=sendkey), data=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("code") == 0:
            print("Server酱推送成功（微信+APP已收到）")
            return True
        else:
            print(f"Server酱推送失败：{result.get('message')}")
            return False
    except Exception as e:
        print(f"Server酱推送异常：{str(e)}")
        return False

def main():
    """主函数：抓取→过滤→清理→存储→推送"""
    print(f"===== 开始执行NGA抓取任务 {datetime.now()} =====")
    
    # 1. 抓取并解析3天内的回复
    crawl_result = fetch_nga_posts()
    if crawl_result["status"] == "failed":
        print(f"抓取失败：{crawl_result['error']}")
        # 推送失败提醒
        push_to_serverchan([{
            "post_content": f"抓取失败：{crawl_result['error']}", 
            "post_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "thread_title": "抓取异常提醒",
            "thread_url": NGA_URL
        }])
        exit(1)
    
    # 2. 推送3天内的新回复
    push_to_serverchan(crawl_result["new_posts"])
    
    print(f"===== 任务执行完成 {datetime.now()} =====")

if __name__ == "__main__":
    main()
