import os
import sys
from datetime import datetime
import requests
import yfinance as yf
import math

# 1. 配置你的总预算
TOTAL_BUDGET = 30000.0

# 2. 监控池：包含个股名称、报警区间，以及对应的资金百分比
MONITOR_POOL = {
    "VOO":  {"name": "标普500-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0},
    "QQQ":  {"name": "纳指100-ETF", "min": 5.0, "max": 10.0, "risk_pct": 20.0},
    "AAPL": {"name": "苹果",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MSFT": {"name": "微软",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "NVDA": {"name": "英伟达",     "min": 5.0, "max": 10.0, "risk_pct": 8.0},
    "GOOG": {"name": "谷歌-C",     "min": 5.0, "max": 10.0, "risk_pct": 6.0},  # 🟢 已经完美升级为谷歌C(GOOG)
    "AMZN": {"name": "亚马逊",     "min": 5.0, "max": 10.0, "risk_pct": 6.0},
    "META": {"name": "Meta",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "TSLA": {"name": "特斯拉",     "min": 6.0, "max": 12.0, "risk_pct": 5.0},
    "AVGO": {"name": "博通",       "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "MU":   {"name": "美光科技",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "ASML": {"name": "阿斯麦",     "min": 5.0, "max": 10.0, "risk_pct": 5.0},
    "PLTR": {"name": "Palantir",   "min": 6.0, "max": 12.0, "risk_pct": 4.0},
    "RKLB": {"name": "Rocket Lab", "min": 7.0, "max": 15.0, "risk_pct": 3.0}
}

FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK")

def send_feishu_notification(title, markdown_content):
    if not FEISHU_WEBHOOK:
        print("未配置 FEISHU_WEBHOOK，取消发送")
        return
        
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": markdown_content
                }
            ]
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, json=payload)
        print(f"【飞书网关响应】: {response.text}")
    except Exception as e:
        print(f"发送飞书消息失败: {e}")

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

            # 1. 拿到近30个交易日的最高价
            recent_high = df["High"].tail(30).max()
            
            # 2. 优先使用 fast_info 里的实时/最后收盘价，彻底对齐昨日最新收盘价
            current_price = stock.fast_info.get('lastPrice')
            
            # 如果 fast_info 没抓到有效数字，再用常规历史数据兜底
            if current_price is None or math.isnan(current_price):
                for i in range(1, len(df) + 1):
                    price_check = df["Close"].iloc[-i]
                    if not math.isnan(price_check):
                        current_price = price_check
                        break
            
            if current_price is None or math.isnan(current_price):
                print(f"[{ticker}] 无法捕获到任何有效当前价，跳过")
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
                content = (
                    f"### 🎯 触发【{min_drop}% ~ {max_drop}%】量化建仓点\n"
                    f"**股票/基金**: {name} ({ticker})\n"
                    f"**实时当前价**: `${current_price:.2f}` (较近期高点回调了 `-{drawdown:.2f}%`)\n\n"
                    f"--- \n"
                    f"### ⚙️ 确切实操下单指令：\n"
                    f"1. 操作动作: **买入 / BUY** 🟢\n"
                    f"2. 确切代码: `{ticker}`\n"
                    f"3. 确切数量: **` {exact_shares} ` 股**\n"
                    f"4. 预计资金: `${actual_spent:.2f}`\n\n"
                    f"💡 请检查账户中的后备子弹是否充足。"
                )
                send_feishu_notification(title, content)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产触及设定的加仓线。")

if __name__ == "__main__":
    check_drawdown()
    
    # 强制飞书实验触发器
    print("--- 正在触发飞书送达实验 ---")
    test_title = "📢【实操买入指令】测试：购买 纳指100-ETF(QQQ) 5股"
    test_content = (
        f"### 🎯 飞书实验成功！已成功链接云端量化卫士\n"
        f"**测试标的**: 纳指100-ETF (QQQ)\n"
        f"**实时模拟价**: `$740.00` (较近期高点回调了 `-5.20%`)\n\n"
        f"--- \n"
        f"### ⚙️ 今晚 21:30 开盘手动打底仓指令：\n"
        f"1. 操作动作: **买入 / BUY** 🟢\n"
        f"2. 确切代码: `QQQ`\n"
        f"3. 确切数量: **` 5 ` 股** (抗踏空核心底仓)\n"
        f"4. 预计资金: `$3,700.00` (基于你的3万美元总预算)\n\n"
        f"💡 **下一步行动**：收到本条代表飞书通信完全正常。今晚开盘可照此手动打入 VOO 6股和 QQQ 5股底仓，剩下的 75% 资金静待飞书真实的暴跌警报！"
    )
    send_feishu_notification(test_title, test_content)
