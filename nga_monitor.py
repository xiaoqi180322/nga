import json
import requests
from bs4 import BeautifulSoup
import os

# ---------------------- 必改配置（替换成你的信息） ----------------------
# 目标用户authorid（就是你链接里的150058）
TARGET_UID = os.getenv("NGA_UID", "150058")
# Server酱KEY（用于推送到微信）
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "SCT314606TD2vODo7oR8UKhyZAw6oKKyGz")
# NGA登录Cookie（必须填，否则抓不到回复）
NGA_COOKIE = os.getenv("NGA_COOKIE", "ngacn0comUserInfo=%25D0%25C4%25BA%25A3%09%25E5%25BF%2583%25E6%25B5%25B7%0939%0939%09%0910%0934936%094%090%09207%2C347%2C84%0961_4%2C-7_30; _178i=1; ngaPassportUid=535794; ngaPassportUrlencodedUname=%25D0%25C4%25BA%25A3; ngaPassportCid=X9oj2iogsjgju542lgfqbkc31uvpb8n0iidtoted; Hm_lvt_2728f3eacf75695538f5b1d1b5594170=1770682296,1770857648,1770969101,1771001633; HMACCOUNT=27B56921B761C67A; ngacn0comUserInfoCheck=317ea4545cd951307fd82fd586a0f872; ngacn0comInfoCheckTime=1771017192; lastvisit=1771017843; lastpath=/thread.php?searchpost=1&authorid=150058; bbsmisccookies=%7B%22uisetting%22%3A%7B0%3A1%2C1%3A1771468450%7D%2C%22pv_count_for_insad%22%3A%7B0%3A-18%2C1%3A1771088472%7D%2C%22insad_views%22%3A%7B0%3A1%2C1%3A1771088472%7D%7D; Hm_lpvt_2728f3eacf75695538f5b1d1b5594170=1771017843")

# 存储已处理回复的文件
PROCESSED_REPLIES = "nga_replies.json"
# 正确的NGA域名和回复搜索地址
NGA_BASE_URL = "https://nga.178.com"
REPLY_SEARCH_URL = f"{NGA_BASE_URL}/thread.php?searchpost=1&authorid={TARGET_UID}"

# ---------------------- 核心工具函数 ----------------------
def get_headers(referer=NGA_BASE_URL):
    """生成带Cookie的请求头，适配nga.178.com域名"""
    return {
        "Cookie": NGA_COOKIE,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/121.0.0.0 Safari/537.36",
        "Referer": referer,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Host": "nga.178.com"  # 关键：指定正确的Host
    }

def load_processed():
    """加载已监控过的回复ID"""
    try:
        with open(PROCESSED_REPLIES, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except FileNotFoundError:
        print("ℹ️ 首次运行，未找到历史记录文件，将自动创建")
        return set()

def save_processed(processed_ids):
    """保存已监控的回复ID"""
    with open(PROCESSED_REPLIES, "w", encoding="utf-8") as f:
        json.dump(list(processed_ids), f)
    print("✅ 历史回复记录已保存")

def push_wechat(content):
    """推送到微信"""
    if not SERVERCHAN_KEY or SERVERCHAN_KEY == "你的Server酱KEY":
        print("⚠️ 未配置Server酱KEY，跳过推送（如需推送请填写有效KEY）")
        return
    try:
        res = requests.post(
            f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send",
            data={"title": f"NGA用户{TARGET_UID}新回复", "desp": content},
            timeout=10
        )
        if res.json()["code"] == 0:
            print("✅ 新回复已成功推送到微信！")
        else:
            print(f"❌ 推送失败：{res.text}")
    except Exception as e:
        print(f"❌ 推送异常：{str(e)}")

# ---------------------- 抓取目标用户的所有回复（适配正确地址） ----------------------
def fetch_user_replies():
    """抓取目标用户在NGA发布的所有回复（使用正确的搜索地址）"""
    print(f"🔍 开始抓取用户{TARGET_UID}的回复列表（地址：{REPLY_SEARCH_URL}）...")
    headers = get_headers(referer=REPLY_SEARCH_URL)
    
    try:
        # 发起请求（关闭SSL验证，避免部分环境报错）
        res = requests.get(
            REPLY_SEARCH_URL,
            headers=headers,
            timeout=15,
            verify=False  # 适配部分环境的SSL问题
        )
        res.raise_for_status()
        # 正确解码页面（NGA是GBK/GB2312编码）
        res.encoding = "gbk"
        soup = BeautifulSoup(res.text, "html.parser")
        
        replies = []
        # 适配nga.178.com的回复列表结构
        # 遍历所有回复项（核心选择器适配）
        for reply_item in soup.select(".postlist > div"):
            # 提取帖子标题和链接
            post_title_elem = reply_item.select_one("a[href*='tid=']")
            if not post_title_elem:
                continue
            post_title = post_title_elem.get_text(strip=True)
            post_href = post_title_elem.get("href")
            # 拼接完整的帖子链接
            if not post_href.startswith("http"):
                post_url = f"{NGA_BASE_URL}/{post_href}"
            else:
                post_url = post_href
            # 提取帖子ID（tid）
            post_tid = post_href.split("tid=")[-1].split("&")[0] if "tid=" in post_href else "未知"
            
            # 提取回复楼层和时间
            info_elem = reply_item.select_one(".authorinfo")
            if info_elem:
                info_text = info_elem.get_text(strip=True)
                # 提取楼层号（格式：#123 楼）
                floor_num = ""
                for part in info_text.split():
                    if part.startswith("#") and part.endswith("楼"):
                        floor_num = part.replace("#", "").replace("楼", "")
                        break
                # 提取回复时间
                reply_time = ""
                if "发表于" in info_text:
                    reply_time = info_text.split("发表于")[-1].strip()
            else:
                floor_num = "未知楼层"
                reply_time = "未知时间"
            
            # 提取回复内容
            content_elem = reply_item.select_one(".postcontent")
            reply_content = content_elem.get_text(strip=True) if content_elem else "无内容"
            
            # 生成唯一回复ID（帖子ID_楼层号）
            reply_id = f"{post_tid}_{floor_num}" if floor_num else f"{post_tid}_{len(replies)+1}"
            
            replies.append({
                "reply_id": reply_id,
                "post_title": post_title,
                "post_url": post_url,
                "floor_num": floor_num,
                "reply_time": reply_time,
                "content": reply_content
            })
        
        print(f"✅ 回复抓取完成！共抓取到{len(replies)}条历史回复")
        return replies
    except Exception as e:
        print(f"❌ 抓取回复失败：{str(e)}")
        return []

# ---------------------- 主逻辑 ----------------------
def main():
    print("="*50)
    print("🚀 NGA用户新回复监控脚本启动（适配nga.178.com）")
    print("="*50)
    
    # 1. 校验关键配置
    print("\n🔧 开始校验配置...")
    config_ok = True
    if not NGA_COOKIE or NGA_COOKIE == "你的NGA完整Cookie":
        print("❌ 配置错误：未填写有效NGA Cookie！")
        config_ok = False
    else:
        print("✅ Cookie配置校验通过")
    
    if not TARGET_UID:
    print("❌ 配置错误：未填写要监控的用户authorid！")
    config_ok = False
    else:
    print(f"✅ 监控目标authorid校验通过：{TARGET_UID}")
    
    if not SERVERCHAN_KEY or SERVERCHAN_KEY == "你的Server酱KEY":
        print("⚠️ 配置提醒：未填写Server酱KEY（仅影响推送，不影响监控）")
    else:
        print("✅ Server酱KEY配置校验通过")
    
    if not config_ok:
        print("\n❌ 核心配置错误，脚本终止运行！")
        return
    print("✅ 所有核心配置校验通过！")

    # 2. 加载历史记录
    print("\n📜 加载历史回复记录...")
    processed_ids = load_processed()
    print(f"✅ 历史记录加载完成，已监控{len(processed_ids)}条回复")

    # 3. 抓取回复
    all_replies = fetch_user_replies()
    if not all_replies:
        print("ℹ️ 未抓取到任何回复（可能是Cookie失效/UID错误/用户无回复）")
        return

    # 4. 筛选新回复
    new_replies = [r for r in all_replies if r["reply_id"] not in processed_ids]
    
    if new_replies:
        print(f"\n🎉 发现{len(new_replies)}条新回复！")
        # 拼接推送内容
        push_text = ""
        for idx, reply in enumerate(new_replies, 1):
            push_text += f"""
【新回复{idx}】
帖子：{reply['post_title']}
楼层：{reply['floor_num']}
时间：{reply['reply_time']}
内容：{reply['content']}
链接：{reply['post_url']}
---
"""
        print(push_text)
        # 推送+标记为已处理
        push_wechat(push_text)
        processed_ids.update([r["reply_id"] for r in new_replies])
        save_processed(processed_ids)
    else:
        print("\nℹ️ 暂无新回复，脚本运行正常！")
        # 首次运行时保存历史记录
        if len(processed_ids) == 0:
            print("📝 首次运行，保存所有历史回复（避免后续重复推送）")
            save_processed(processed_ids.union([r["reply_id"] for r in all_replies]))

    print("\n="*50)
    print("✅ 脚本运行完成，全程无异常！")
    print("="*50)

if __name__ == "__main__":
    main()
