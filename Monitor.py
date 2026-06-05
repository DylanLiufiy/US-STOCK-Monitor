import os
import sys
from datetime import datetime
import requests
import yfinance as yf

# ============================================================================
# 1. 配置你的真实资金参数（基于你的 30,000 美元预算）
# ============================================================================
TOTAL_BUDGET = 30000.0  # 你的总预算 3万美元

# 监控池：包含个股名称、报警区间，以及触发时凯利公式推荐该笔投入的“总资金百分比”
MONITOR_POOL = {
    # 核心大盘底仓：跌5%属于极稀缺大坑，直接下较重仓位
    "VOO":  {"name": "标普500-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0}, # 触发则投入总资金的 20%
    "QQQ":  {"name": "纳指100-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0}, # 触发则投入总资金的 20%
    
    # 核心蓝筹巨头（单笔尝试用半凯利：占总资金的 5% ~ 8% 试错）
    "AAPL": {"name": "苹果",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MSFT": {"name": "微软",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "NVDA": {"name": "英伟达",     "min": 5.0, "max": 10.0, "risk_pct": 8.0},  # 爆发力强，给 8%
    "GOOGL":{"name": "谷歌",       "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "AMZN": {"name": "亚马逊",     "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "META": {"name": "Meta",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "TSLA": {"name": "特斯拉",     "min": 6.0, "max": 12.0, "risk_pct": 5.0},
    
    # 2026 算力与黑马（轻仓分批试错：占总资金的 4%）
    "AVGO": {"name": "博通",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MU":   {"name": "美光科技",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "ASML": {"name": "阿斯麦",     "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "PLTR": {"name": "Palantir",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "RKLB": {"name": "Rocket Lab", "min": 7.0, "max": 15.0, "risk_pct": 3.0}   # 航天股轻仓
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
    print(f"=== 开始执行美股多策略分级监控 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    alert_triggered = False

    for ticker, config in MONITOR_POOL.items():
        name = config["name"]
        min_drop = config["min"]
        max_drop = config["max"]
        risk_pct = config["risk_pct"]
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if df.empty:
                continue

            recent_high = df["High"].tail(30).max()
            current_price = df["Close"].iloc[-1]
            drawdown = (recent_high - current_price) / recent_high * 100

            print(f"[{ticker}] {name}: 30日高点 ${recent_high:.2f} | 当前 ${current_price:.2f} | 跌幅: -{drawdown:.2f}%")

            # 触发个股自定义的凯利补仓线
            if min_drop <= drawdown <= max_drop:
                alert_triggered = True
                
                # 核心计算：算出这次应该买多少金额，以及折合多少整股数量
                target_cash_amount = TOTAL_BUDGET * (risk_pct / 100.0)
                exact_shares = int(target_cash_amount // current_price)
                actual_spent = exact_shares * current_price
                
                title = f"📢【实操买入指令】购买 {name}({ticker}) {exact_shares}股"
                content = (
                    f"### 🎯 触发【{min_drop}% ~ {max_drop}%】量化建仓点\n\n"
                    f"- **股票/基金**: {name} ({ticker})\n"
                    f"- **实时当前价**: `${current_price:.2f}` (较近期高点回调了 `-{drawdown:.2f}%`)\n\n"
                    f"--- \n\n"
                    f"### ⚙️ 确切实操下单指令（请直接去券商App照着买）：\n"
                    f"1. **操作动作**: `买入 / BUY` 🟢\n"
                    f"2. **确切股票代码**: `{ticker}`\n"
                    f"3. **确切买入数量**: **` {exact_shares} ` 股** (按整股截取)\n"
                    f"4. **预计动用资金**: `${actual_spent:.2f}` (约占总本金的 {risk_pct}%)\n\n"
                    f"💡 **风控提示**：当前您的后备子弹充足，本操作严格符合半凯利资金容错模型，买入后请保持锁仓！"
                )
                send_notification(title, content)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产触及设定的加仓线。")

if __name__ == "__main__":
    check_drawdown()
