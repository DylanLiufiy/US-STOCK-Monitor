import os
import urllib.parse
import requests

# 🔒 从 GitHub 保险箱中强行抓取密匙
BARK_KEY = os.environ.get("BARK_KEY")


def test_push():
    print("🧪 正在启动【Bark 手机链路连通性极限测试】...")

    if not BARK_KEY:
        print("❌ 致命错误：GitHub 环境变量完全没有读取到 BARK_KEY！")
        print("💡 解决办法：说明您 Settings 里的保险箱名字写错了，或者大小写不对。")
        return

    print(f"📡 成功抓取到保险箱密匙，前四位为: {BARK_KEY[:4]}... (正在进行网络拼接)")

    # 剔除用户可能不小心误粘贴进去的网址前缀和斜杠，实现底层净化
    clean_key = BARK_KEY.replace("https://day.app", "").strip("/")

    title = "🔔 恭喜！Bark 链路完全打通"
    content = "这是来自 GitHub 海外服务器的最高优先级连通性测试信。看到这条消息说明您的自动化环境已经 100% 完美无瑕！"

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)

    # 拼接合法合规的官方 API 终点
    url = f"https://day.app{clean_key}/{encoded_title}/{encoded_content}?group=链路测试&sound=bell"

    try:
        print(f"🌐 正在向苹果 APNS 服务器发送网络请求...")
        res = requests.get(url, timeout=15)
        print(f"📊 服务器响应状态码 (HTTP Status): {res.status_code}")
        print(f"📝 服务器返回原始内容: {res.text}")

        if res.status_code == 200:
            print(
                "🏁 【云端发送完毕】GitHub 已经成功把信交给了苹果服务器！请立刻检查手机！"
            )
        else:
            print(
                "❌ 苹果服务器拒绝了这次请求，请检查您粘贴的 KEY 字符串是否多打了空格或打错了字母。"
            )
    except Exception as e:
        print(f"❌ 网络发生严重阻塞崩溃: {e}")


if __name__ == "__main__":
    test_push()
