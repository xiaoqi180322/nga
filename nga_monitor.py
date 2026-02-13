import requests
from bs4 import BeautifulSoup
import os
import time

# 读取环境变量（从GitHub Secrets传入）
nga_uid = os.getenv("NGA_UID")
send_key = os.getenv("SERVERCHAN_KEY")

# 已推送的帖子ID（本次运行临时存储）
posted_tids = set()

# NGA请求头（加登录Cookie）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": os.getenv("NGA_COOKIE", "")  # 从Secrets读取Cookie
}

def fetch_user_posts():
    """抓取NGA用户主页的帖子列表"""
    if not nga_uid:
        print("错误：未配置NGA_UID")
        return "未知用户", []
    
    url = f"https://bbs.nga.cn/nuke.php?uid={nga_uid}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 提取用户名
        username_elem = soup.select_one(".usertop .username")
        username = username_elem.text.strip() if username_elem else "未知用户"
        
        # 提取帖子信息
        posts = soup.select(".topic_row")
        post_list = []
        for post in posts:
            tid = post.get("data-tid")
            title_elem = post.select_one(".topic_title")
            if tid and title_elem:
                title = title_elem.text.strip()
                content_elem = post.select_one(".topic_content")
                content = content_elem.text.strip()[:200] if content_elem else ""
                post_list.append({
                    "tid": tid,
                    "title": title,
                    "content": content
                })
        return username, post_list
    except Exception as e:
        print(f"抓取失败：{str(e)}")
        return "未知用户", []

def push_to_wechat(username, title, tid, content):
    """推送到微信（Server酱）"""
    if not send_key:
        print("错误：未配置SERVERCHAN_KEY")
        return
    
    push_url = f"https://sctapi.ftqq.com/{send_key}.send"
    # 单行字符串，避免任何换行冲突
    desp = f"**发帖人**：{username}\n**帖子标题**：{title}\n**帖子链接**：https://bbs.nga.cn/read.php?tid={tid}\n**发布时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n\n内容预览：{content}..."
    data = {
        "title": f"【NGA】{username}发布新帖",
        "desp": desp
    }
    
    try:
        resp = requests.post(push_url, data=data, timeout=10)
        print(f"推送结果：{resp.text}")
    except Exception as e:
        print(f"推送失败：{str(e)}")

def main():
    """主逻辑"""
    username, posts = fetch_user_posts()
    if not posts:
        print("暂无帖子/抓取失败")
        return
    
    # 筛选新帖并推送
    new_posts = [p for p in posts if p["tid"] not in posted_tids]
    if new_posts:
        print(f"发现{len(new_posts)}条新帖")
        for post in new_posts:
            push_to_wechat(username, post["title"], post["tid"], post["content"])
            posted_tids.add(post["tid"])
    else:
        print("暂无新帖")

if __name__ == "__main__":
    main()
