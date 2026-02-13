import requests
from datetime import datetime, timedelta
import os
from bs4 import BeautifulSoup
import re
import pytz

# ===== 配置区 =====
NGA_UID = "150058"
NGA_URL = f"https://nga.178.com/thread.php?searchpost=1&authorid={NGA_UID}"
SERVERCHAN_URL = "https://sctapi.ftqq.com/{sendkey}.send"
DAYS_TO_KEEP = 3  # 仅关注近3天的新回复

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": os.getenv("NGA_COOKIE"),
    "Referer": "https://nga.178.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}

# ===== 全局去重集合（内存中记录已推送的 post_id） =====
PUSHED_POST_IDS = set()

# ===== 北京时间工具函数 =====
def get_beijing_time():
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz)

def beijing_time_str(fmt="%Y-%m-%d %H:%M:%S"):
    return get_beijing_time().strftime(fmt)

# ===== 通用推送函数 =====
def send_serverchan_msg(title, desp):
    """通用推送函数：封装Server酱推送逻辑"""
    sendkey = os.getenv("SERVERCHAN_SENDKEY")
    if not sendkey:
        print(f"❌ 未配置Server酱SendKey，无法推送【{title}】")
        return False

    try:
        data = {"title": title, "desp": desp}
        response = requests.post(SERVERCHAN_URL.format(sendkey=sendkey), data=data, timeout=15)
        response.raise_for_status()
        result = response.json()
        if result.get("code") == 0:
            print(f"✅ 【{title}】推送成功！")
            return True
        else:
            print(f"❌ 【{title}】推送失败: {result.get('message')}")
            return False
    except Exception as e:
        print(f"❌ 【{title}】推送异常: {str(e)}")
        return False

# ===== 测试逻辑（返回测试结果和失败原因） =====
def run_all_tests():
    """执行所有测试，返回测试结果汇总"""
    test_results = {
        "overall": True,
        "nga_conn": {"status": True, "msg": ""},
        "serverchan": {"status": True, "msg": ""}
    }

    # 测试1：NGA连接与Cookie
    try:
        response = requests.get(NGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = "gbk"
        if "登录" in response.text[:2000] or "请先登录" in response.text[:2000]:
            test_results["nga_conn"]["status"] = False
            test_results["nga_conn"]["msg"] = "Cookie无效或已过期，页面被重定向到登录页"
            test_results["overall"] = False
        else:
            test_results["nga_conn"]["msg"] = "连接正常，Cookie有效"
    except requests.exceptions.RequestException as e:
        test_results["nga_conn"]["status"] = False
        test_results["nga_conn"]["msg"] = f"网络异常：{str(e)}"
        test_results["overall"] = False

    # 测试2：Server酱配置
    sendkey = os.getenv("SERVERCHAN_SENDKEY")
    if not sendkey:
        test_results["serverchan"]["status"] = False
        test_results["serverchan"]["msg"] = "未配置SendKey"
        test_results["overall"] = False
    else:
        test_results["serverchan"]["msg"] = "SendKey已配置"

    return test_results

# ===== 核心监控功能 =====
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

            # 抓取完整回复内容
            content_elem = item.find("div", class_="postcontent")
            if content_elem:
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
                "post_content": post_content,
                "crawl_time": beijing_time_str()
            }
            valid_posts.append(post_info)
        except Exception as e:
            print(f"解析单条回复失败: {e}")
            continue

    return valid_posts

def fetch_new_posts():
    try:
        response = requests.get(NGA_URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
        response.encoding = "gbk"
        all_posts = parse_nga_posts(response.text)

        # 筛选出从未推送过的新回复
        new_posts = [p for p in all_posts if p["post_id"] not in PUSHED_POST_IDS]
        # 更新已推送集合
        for p in new_posts:
            PUSHED_POST_IDS.add(p["post_id"])

        return {
            "status": "success",
            "new_posts": new_posts
        }
    except Exception as e:
        # 抓取失败时推送提醒
        fail_title = f"❌ NGA监控抓取失败（UID:{NGA_UID}）"
        fail_desp = f"""
NGA监控抓取失败！
- 失败时间：{beijing_time_str()}
- 错误原因：{str(e)}
- 建议：检查Cookie是否过期或NGA网站是否可访问
        """.strip()
        send_serverchan_msg(fail_title, fail_desp)
        return {
            "status": "failed",
            "error": str(e),
            "new_posts": []
        }

def format_posts_for_push(new_posts):
    if not new_posts:
        return ""

    push_content = ""
    for i, post in enumerate(new_posts, 1):
        push_content += f"""
【新回复 {i}】
- 发布时间：{post['post_time']}
- 帖子标题：{post['thread_title']}
- 帖子链接：{post['thread_url']}
- 完整内容：
{post['post_content']}
        """
    return push_content.strip()

# ===== 主函数（核心：按指定格式推送测试结果） =====
def main():
    print(f"===== 开始执行NGA监控任务 {beijing_time_str()} =====")

    # ========== 1. 执行所有测试并按指定格式推送汇总 ==========
    test_results = run_all_tests()
    
    # 构造测试推送标题和内容（完全匹配你要的格式）
    if test_results["overall"]:
        test_title = "🎉 NGA监控脚本测试成功"
        test_desp = f"""
你的NGA云端监控已部署完成！
- 监控的UID：{NGA_UID if NGA_UID else "未配置"}
- 测试时间：{beijing_time_str()}
- NGA连接状态：✅ {test_results['nga_conn']['msg']}
- 推送配置状态：✅ {test_results['serverchan']['msg']}
- 后续目标用户发新帖会自动推送到微信～
        """.strip()
    else:
        test_title = "⚠️ NGA监控脚本测试失败"
        test_desp = f"""
你的NGA云端监控部署异常！
- 监控的UID：{NGA_UID if NGA_UID else "未配置"}
- 测试时间：{beijing_time_str()}
- NGA连接状态：{"❌ " + test_results['nga_conn']['msg'] if not test_results['nga_conn']['status'] else "✅ " + test_results['nga_conn']['msg']}
- 推送配置状态：{"❌ " + test_results['serverchan']['msg'] if not test_results['serverchan']['status'] else "✅ " + test_results['serverchan']['msg']}
- 请修复以上问题后重新运行脚本～
        """.strip()
    
    # 推送测试汇总
    send_serverchan_msg(test_title, test_desp)

    # ========== 2. 测试通过则执行监控 ==========
    if test_results["overall"]:
        print("\n===== 所有测试通过，进入正式监控流程 =====")
        crawl_result = fetch_new_posts()
        if crawl_result["status"] == "success":
            new_posts = crawl_result["new_posts"]
            if new_posts:
                print(f"发现 {len(new_posts)} 条新回复，正在推送...")
                push_content = format_posts_for_push(new_posts)
                push_title = f"🎉 NGA新回复提醒（UID:{NGA_UID}） {beijing_time_str()}"
                send_serverchan_msg(push_title, push_content)
            else:
                print("暂无3天内的新回复，无需推送")
    else:
        print("\n❌ 测试未通过，跳过监控流程")

    print(f"\n===== 本次监控任务执行完成 {beijing_time_str()} =====")

if __name__ == "__main__":
    main()
