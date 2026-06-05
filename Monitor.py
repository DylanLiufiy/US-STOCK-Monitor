import os
import sys
from datetime import datetime
import requests
import yfinance as yf

# 1. 定义监控的“七姐妹”美股代码
MAG_SEVEN = {
    # 1. 传统七姐妹
    "AAPL": "苹果",
    "MSFT": "微软",
    "NVDA": "英伟达",
    "GOOGL": "谷歌",
    "AMZN": "亚马逊",
    "META": "Meta",
    "TSLA": "特斯拉",
    # 2. 2026 算力/半导体核心巨头
    "AVGO": "博通",
    "MU": "美光科技",
    "ASML": "阿斯麦",
    "LRCX": "泛林集团",
    # 3. AI软件与商业化颠覆者
    "PLTR": "Palantir",
    "CRM": "Salesforce",
    # 4. 生物医药与高壁垒硬科技
    "LLY": "礼来",
    "RKLB": "Rocket Lab"
}

# 从 GitHub Secrets 中安全地读取 Key
SERVER_CHAN_KEY = os.environ.get("SERVER_CHAN_KEY")


def send_notification(title, content):
    if not SERVER_CHAN_KEY:
        print("未配置 SERVER_CHAN_KEY，取消发送")
        return
    url = f"https://ftqq.com{SERVER_CHAN_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data)
        print(f"【已发送提醒】: {title}")
    except Exception as e:
        print(f"发送消息失败: {e}")


def check_drawdown():
    print(
        f"开始检查七姐妹股价 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
    )
    alert_triggered = False

    for ticker, name in MAG_SEVEN.items():
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if df.empty:
                continue

            recent_high = df["High"].tail(30).max()
            current_price = df["Close"].iloc[-1]
            drawdown = (recent_high - current_price) / recent_high * 100

            print(
                f"{name}({ticker}): 30日高点 ${recent_high:.2f} | 当前 ${current_price:.2f} | 回调: {drawdown:.2f}%"
            )

            # 触发核心逻辑：回调在 5% ~ 10% 之间时报警
            if 5.0 <= drawdown <= 10.0:
                alert_triggered = True
                title = f"🚨 凯利机会：{name}({ticker})回调 {drawdown:.1f}%"
                content = (
                    f"### 🎯 触发【5%~10%】第一批金字塔补仓线\n\n"
                    f"- **股票**: {name} ({ticker})\n"
                    f"- **30日最高点**: `${recent_high:.2f}`\n"
                    f"- **当前最新价**: `${current_price:.2f}`\n"
                    f"- **当前回调幅度**: `-{drawdown:.2f}%`\n\n"
                    f"请检查你的凯利后备资金，合理安排 3万美元 的分批加仓！"
                )
                send_notification(title, content)
        except Exception as e:
            print(f"获取 {ticker} 数据失败: {e}")

    if not alert_triggered:
        print("没有股票触发回调，无需报警。")


if __name__ == "__main__":
    check_drawdown()
