import requests
from bs4 import BeautifulSoup
import os
import time

# 读取环境变量（从GitHub Secrets传入）
nga_uid = os.getenv("NGA_UID")
send_key = os.getenv("SERVERCHAN_KEY")
nga_cookie = os.getenv("NGA_COOKIE", "")  # 可选：NGA登录Cookie

# 已推送的帖子ID（本次运行临时存储）
posted_tids = set()

# NGA请求头（模拟浏览器，可加Cookie）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": nga_cookie  # 带上登录Cookie，解决抓取失败
}

def push_to_wechat(title, desp):
    """通用推送函数（测试/正常推送都用这个）"""
    if not send_key:
        print("错误：未配置SERVERCHAN_KEY（Server酱的SendKey）")
        return False
    
    # 发送推送请求到Server酱
    push_url = f"https://sctapi.ftqq.com/{send_key}.send"
    data = {"title": title, "desp": desp}
    try:
        resp = requests.post(push_url, data=data, timeout=10)
        print(f"推送结果：{resp.text}")
        return True
    except Exception as e:
        print(f"推送失败：{str(e)}")
        return False

def fetch_user_posts():
    """抓取NGA用户帖子（带Cookie）"""
    if not nga_uid:
        print("错误：未配置NGA_UID（目标用户的数字ID）")
        return "未知用户", []
    
    # 访问用户主页
    url = f"https://bbs.nga.cn/nuke.php?uid={nga_uid}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # 提取用户名
        username_elem = soup.select_one(".usertop .username")
        username = username_elem.text.strip() if username_elem else "未知用户"
        
        # 提取帖子列表
        posts = soup.select(".topic_row")
        post_list = []
        for post in posts:
            tid = post.get("data-tid")
            title_elem = post.select_one(".topic_title")
            if tid and title_elem:
                title = title_elem.text.strip()
                content_elem = post.select_one(".topic_content")
                content = content_elem.text.strip()[:200] if content_elem else ""
                post_list.append({"tid": tid, "title": title, "content": content})
        
        print(f"抓取成功：找到{len(post_list)}条帖子")
        return username, post_list
    except Exception as e:
        print(f"抓取失败：{str(e)}（大概率是UID错/未加NGA登录Cookie）")
        return "未知用户", []

def main():
    """主逻辑：先发测试推送，再监控帖子"""
    # ========== 1. 发送测试推送（核心新增部分） ==========
    test_title = "🎉 NGA监控脚本测试成功"
    test_desp = f"""
你的NGA云端监控已部署完成！
- 监控的UID：{nga_uid if nga_uid else "未配置"}
- 测试时间：{time.strftime('%Y-%m-%d %H:%M:%S')}
- 后续目标用户发新帖会自动推送到微信～

如果提示抓取失败，需：
1. 核对NGA_UID是否为纯数字；
2. 添加NGA登录Cookie到Secrets（名称：NGA_COOKIE）。
    """.strip()
    
    # 发送测试消息
    test_success = push_to_wechat(test_title, test_desp)
    if test_success:
        print("✅ 测试推送已发送，微信请查收！")
    else:
        print("❌ 测试推送失败，检查SERVERCHAN_KEY！")

    # ========== 2. 正常监控帖子 ==========
    username, posts = fetch_user_posts()
    if not posts:
        print("ℹ️ 暂无帖子/抓取失败（不影响推送功能）")
        return
    
    # 筛选新帖并推送
    new_posts = [p for p in posts if p["tid"] not in posted_tids]
    if new_posts:
        print(f"🔔 发现{len(new_posts)}条新帖，开始推送！")
        for post in new_posts:
            desp = f"""
**发帖人**：{username}
**帖子标题**：{post['title']}
**帖子链接**：https://bbs.nga.cn/read.php?tid={post['tid']}
**发布时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}

内容预览：{post['content']}...
            """.strip()
            push_to_wechat(f"【NGA】{username}发布新帖", desp)
            posted_tids.add(post["tid"])
    else:
        print("ℹ️ 暂无新帖")

if __name__ == "__main__":
    main()
