import os
import sys
from datetime import datetime
import requests
import yfinance as yf
import math

# 1. 配置你的总预算（3万美元本金）
TOTAL_BUDGET = 30000.0

# 2. 智能分级监控池
MONITOR_POOL = {
    "VOO":  {"name": "标普500-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0},
    "QQQ":  {"name": "纳指100-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0},
    "AAPL": {"name": "苹果",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MSFT": {"name": "微软",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "NVDA": {"name": "英伟达",     "min": 5.0, "max": 10.0, "risk_pct": 8.0},
    "GOOG": {"name": "谷歌-C",     "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "AMZN": {"name": "亚马逊",     "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "META": {"name": "Meta",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "TSLA": {"name": "特斯拉",     "min": 6.0, "max": 12.0, "risk_pct": 5.0},
    "AVGO": {"name": "博通",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MU":   {"name": "美光科技",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "ASML": {"name": "阿斯麦",     "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "PLTR": {"name": "Palantir",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "RKLB": {"name": "Rocket Lab", "min": 7.0, "max": 15.0, "risk_pct": 3.0}
}

BARK_URL = os.environ.get("BARK_URL")

def send_bark_notification(title, body):
    if not BARK_URL:
        print("未配置 BARK_URL，取消发送")
        return
        
    base_url = BARK_URL if BARK_URL.endswith("/") else BARK_URL + "/"
    encoded_title = requests.utils.quote(title)
    encoded_body = requests.utils.quote(body)
    url = f"{base_url}{encoded_title}/{encoded_body}"
    
    # 注入高级参数：使用极为清脆醒目的金融投资警报音(bell)
    params = {"sound": "bell", "group": "美股凯利监控"}
    
    try:
        response = requests.get(url, params=params)
        print(f"【Bark 原生网关响应】: {response.text}")
    except Exception as e:
        print(f"发送 Bark 独立消息失败: {e}")

def check_drawdown():
    print(f"=== 开始执行美股多策略分级监控 ===")
    alert_triggered = False

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })

    for ticker, config in MONITOR_POOL.items():
        name = config["name"]
        min_drop = config["min"]
        max_drop = config["max"]
        risk_pct = config["risk_pct"]
        
        try:
            stock = yf.Ticker(ticker, session=session)
            df = stock.history(period="60d")
            if df.empty:
                continue

            recent_high = df["High"].tail(30).max()
            current_price = stock.fast_info.get('lastPrice')
            
            if current_price is None or math.isnan(current_price):
                for i in range(1, len(df) + 1):
                    price_check = df["Close"].iloc[-i]
                    if not math.isnan(price_check):
                        current_price = price_check
                        break
            
            if current_price is None or math.isnan(current_price):
                continue

            drawdown = (recent_high - current_price) / recent_high * 100
            print(f"[{ticker}] {name}: 30日高点 ${recent_high:.2f} | 最新价 ${current_price:.2f} | 真实跌幅: -{drawdown:.2f}%")

            if min_drop <= drawdown <= max_drop:
                alert_triggered = True
                target_cash_amount = TOTAL_BUDGET * (risk_pct / 100.0)
                exact_shares = int(target_cash_amount // current_price)
                actual_spent = exact_shares * current_price
                
                if exact_shares == 0:
                    continue
                    
                title = f"📢【实操买入指令】购买 {name}({ticker}) {exact_shares}股"
                body = (
                    f"触发区间: {min_drop}%~{max_drop}% 量化建仓点。\n"
                    f"最新有效价: ${current_price:.2f} (已大幅回撤 -{drawdown:.2f}%)\n"
                    f"1. 动作: 买入 / BUY 🟢\n"
                    f"2. 代码: {ticker}\n"
                    f"3. 数量: {exact_shares} 股\n"
                    f"4. 动用资金: ${actual_spent:.2f}"
                )
                send_bark_notification(title, body)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产触及设定的加仓线，系统继续保持静默。")

if __name__ == "__main__":
    check_drawdown()
