import json
import requests
from bs4 import BeautifulSoup
import os

# ---------------------- 必改配置（替换成你的信息） ----------------------
# 要监控的NGA用户UID（数字，比如123456）
TARGET_UID = os.getenv("NGA_UID", "150058")
# Server酱KEY（用于推送到微信）
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "SCT314606TD2vODo7oR8UKhyZAw6oKKyGz")
# NGA登录Cookie（必须填，否则抓不到回复）
NGA_COOKIE = os.getenv("NGA_COOKIE", "ngacn0comUserInfo=%25D0%25C4%25BA%25A3%09%25E5%25BF%2583%25E6%25B5%25B7%0939%0939%09%0910%0934936%094%090%09207%2C347%2C84%0961_4%2C-7_30; _178i=1; ngaPassportUid=535794; ngaPassportUrlencodedUname=%25D0%25C4%25BA%25A3; ngaPassportCid=X9oj2iogsjgju542lgfqbkc31uvpb8n0iidtoted; Hm_lvt_2728f3eacf75695538f5b1d1b5594170=1770682296,1770857648,1770969101,1771001633; HMACCOUNT=27B56921B761C67A; ngacn0comUserInfoCheck=317ea4545cd951307fd82fd586a0f872; ngacn0comInfoCheckTime=1771017192; lastvisit=1771017843; lastpath=/thread.php?searchpost=1&authorid=150058; bbsmisccookies=%7B%22uisetting%22%3A%7B0%3A1%2C1%3A1771468450%7D%2C%22pv_count_for_insad%22%3A%7B0%3A-18%2C1%3A1771088472%7D%2C%22insad_views%22%3A%7B0%3A1%2C1%3A1771088472%7D%7D; Hm_lpvt_2728f3eacf75695538f5b1d1b5594170=1771017843")

# 存储已处理回复的文件（自动生成，无需修改）
PROCESSED_REPLIES = "nga_replies.json"
NGA_URL = "https://bbs.nga.cn"

# ---------------------- 核心工具函数 ----------------------
def get_headers(referer=NGA_URL):
    """生成带Cookie的请求头，模拟浏览器"""
    return {
        "Cookie": NGA_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

def load_processed():
    """加载已监控过的回复ID，避免重复推送"""
    try:
        with open(PROCESSED_REPLIES, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_processed(processed_ids):
    """保存已监控的回复ID"""
    with open(PROCESSED_REPLIES, "w", encoding="utf-8") as f:
        json.dump(list(processed_ids), f)

def push_wechat(content):
    """推送到微信"""
    if not SERVERCHAN_KEY:
        print("未配置Server酱KEY，跳过推送")
        return
    try:
        res = requests.post(
            f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send",
            data={"title": f"NGA用户{TARGET_UID}新回复", "desp": content},
            timeout=10
        )
        print("推送成功" if res.json()["code"] == 0 else f"推送失败：{res.text}")
    except Exception as e:
        print(f"推送异常：{str(e)}")

# ---------------------- 抓取目标用户的所有回复 ----------------------
def fetch_user_replies():
    """抓取目标用户在NGA发布的所有回复（核心逻辑）"""
    headers = get_headers()
    # NGA用户回复列表页（直接抓取用户所有回复，无需先抓帖子）
    reply_url = f"{NGA_URL}/nuke.php?func=ucp&uid={TARGET_UID}&type=reply&page=1"
    
    try:
        res = requests.get(reply_url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        replies = []
        # 遍历回复列表，提取关键信息
        for item in soup.select(".plhin tr"):
            # 提取回复关联的帖子信息
            post_link = item.select_one("a[href*='tid=']")
            if not post_link:
                continue
            post_title = post_link.get_text(strip=True)
            post_tid = post_link["href"].split("tid=")[-1].split("&")[0]
            post_url = f"{NGA_URL}/read.php?tid={post_tid}"
            
            # 提取回复楼层和时间
            floor_info = item.select_one(".greyfont").get_text(strip=True)
            floor_num = floor_info.split("楼")[0].split("#")[-1] if "楼" in floor_info else "未知楼层"
            reply_time = floor_info.split("发表于")[-1] if "发表于" in floor_info else "未知时间"
            
            # 提取回复内容（精简版）
            reply_content = item.select_one(".quote").get_text(strip=True) if item.select_one(".quote") else "无内容"
            
            # 生成唯一回复ID（帖子ID_楼层号，防止重复）
            reply_id = f"{post_tid}_{floor_num}"
            
            replies.append({
                "reply_id": reply_id,
                "post_title": post_title,
                "post_url": post_url,
                "floor_num": floor_num,
                "reply_time": reply_time,
                "content": reply_content
            })
        return replies
    except Exception as e:
        print(f"抓取回复失败：{str(e)}")
        return []

# ---------------------- 主逻辑 ----------------------
def main():
    # 校验关键配置
    if not NGA_COOKIE or NGA_COOKIE == "你的NGA完整Cookie":
        print("❌ 请先配置有效的NGA Cookie！")
        return
    if not TARGET_UID or TARGET_UID == "你的目标用户UID":
        print("❌ 请配置要监控的用户UID！")
        return

    print("🔍 开始监控NGA用户新回复...")
    processed_ids = load_processed()
    all_replies = fetch_user_replies()
    
    # 筛选未监控过的新回复
    new_replies = [r for r in all_replies if r["reply_id"] not in processed_ids]
    
    if new_replies:
        print(f"✅ 发现{len(new_replies)}条新回复！")
        # 拼接推送内容
        push_text = ""
        for idx, reply in enumerate(new_replies, 1):
            push_text += f"""
【新回复{idx}】
帖子：{reply['post_title']}
楼层：{reply['floor_num']}
时间：{reply['reply_time']}
内容：{reply['content']}
链接：{reply['reply_url'] if 'reply_url' in reply else reply['post_url']}
---
"""
        # 推送+标记为已处理
        push_wechat(push_text)
        processed_ids.update([r["reply_id"] for r in new_replies])
        save_processed(processed_ids)
    else:
        print("ℹ️ 暂无新回复")

if __name__ == "__main__":
    main()
