import os
import sys
from datetime import datetime
import requests
import yfinance as yf

# 1. 配置你的总预算
TOTAL_BUDGET = 30000.0

# 2. 监控池：包含个股名称、报警区间，以及对应的资金百分比
MONITOR_POOL = {
    "VOO":  {"name": "标普500-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0},
    "QQQ":  {"name": "纳指100-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0},
    "AAPL": {"name": "苹果",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MSFT": {"name": "微软",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "NVDA": {"name": "英伟达",     "min": 5.0, "max": 10.0, "risk_pct": 8.0},
    "GOOGL":{"name": "谷歌",       "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "AMZN": {"name": "亚马逊",     "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "META": {"name": "Meta",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "TSLA": {"name": "特斯拉",     "min": 6.0, "max": 12.0, "risk_pct": 5.0},
    "AVGO": {"name": "博通",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MU":   {"name": "美光科技",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "ASML": {"name": "阿斯麦",     "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "PLTR": {"name": "Palantir",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "RKLB": {"name": "Rocket Lab", "min": 7.0, "max": 15.0, "risk_pct": 3.0}
}

SERVER_CHAN_KEY = os.environ.get("SERVER_CHAN_KEY")

def send_notification(title, content):
    if not SERVER_CHAN_KEY:
        print("未配置 SERVER_CHAN_KEY，取消发送")
        return
    url = f"https://ftqq.com{SERVER_CHAN_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data)
        print(f"【已发送确切指令提醒】: {title}")
    except Exception as e:
        print(f"发送消息失败: {e}")

def check_drawdown():
    print(f"=== 开始执行美股多策略分级监控 ===")
    alert_triggered = False

    # 🟢 终极黑科技：创建一个伪装成标准浏览器的 Session 头部，强行绕过雅虎财经的反爬虫拦截！
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })

    for ticker, config in MONITOR_POOL.items():
        name = config["name"]
        min_drop = config["min"]
        max_drop = config["max"]
        risk_pct = config["risk_pct"]
        
        try:
            # 将伪装头部注入 yfinance
            stock = yf.Ticker(ticker, session=session)
            df = stock.history(period="60d")
            if df.empty:
                print(f"[{ticker}] 获取数据为空，跳过")
                continue

            recent_high = df["High"].tail(30).max()
            current_price = df["Close"].iloc[-1]
            drawdown = (recent_high - current_price) / recent_high * 100

            print(f"[{ticker}] {name}: 30日高点 ${recent_high:.2f} | 当前 ${current_price:.2f} | 真实跌幅: -{drawdown:.2f}%")

            if min_drop <= drawdown <= max_drop:
                alert_triggered = True
                target_cash_amount = TOTAL_BUDGET * (risk_pct / 100.0)
                exact_shares = int(target_cash_amount // current_price)
                actual_spent = exact_shares * current_price
                
                if exact_shares == 0:
                    continue
                    
                title = f"📢【实操买入指令】购买 {name}({ticker}) {exact_shares}股"
                content = (
                    f"### 🎯 触发【{min_drop}% ~ {max_drop}%】量化建仓点\n\n"
                    f"- **股票/基金**: {name} ({ticker})\n"
                    f"- **实时当前价**: `${current_price:.2f}` (较近期高点回调了 `-{drawdown:.2f}%`)\n\n"
                    f"--- \n\n"
                    f"### ⚙️ 确切实操下单指令（请直接去券商App照着买）：\n"
                    f"1. **操作动作**: `买入 / BUY` 🟢\n"
                    f"2. **确切股票代码**: `{ticker}`\n"
                    f"3. **确切买入数量**: **` {exact_shares} ` 股**\n"
                    f"4. **预计动用资金**: `${actual_spent:.2f}`\n\n"
                    f"💡 请检查账户中的后备子弹是否充足。"
                )
                send_notification(title, content)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产触及设定的加仓线。")

if __name__ == "__main__":
    check_drawdown()
