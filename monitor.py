import os
import sys
from datetime import datetime
import requests
import yfinance as yf
import math

# 1. 配置你的总预算（3万美元本金）
TOTAL_BUDGET = 30000.0

# 2. 智能分级监控池：包含个股名称、个性化报警区间，以及对应的凯利资金百分比
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

# 安全读取 iPhone Bark 专属独立网关
BARK_URL = os.environ.get("BARK_URL")

def send_bark_notification(title, body):
    if not BARK_URL:
        print("未配置 BARK_URL，取消发送")
        return
        
    # 自动校准与对齐标准网关的末尾斜杠
    base_url = BARK_URL if BARK_URL.endswith("/") else BARK_URL + "/"
    
    # 对标题和内容进行标准的 URL 编码，彻底防止空格或特殊符号导致拼错网址
    encoded_title = requests.utils.quote(title)
    encoded_body = requests.utils.quote(body)
    url = f"{base_url}{encoded_title}/{encoded_body}"
    
    # 注入高级参数：使用极为清脆醒目的金融投资警报音(bell)
    params = {"sound": "bell", "group": "美股凯利监控"}
    
    try:
        response = requests.get(url, params=params)
        print(f"【Bark 苹果原生网关响应】: {response.text}")
    except Exception as e:
        print(f"发送 Bark 独立消息失败: {e}")

def check_drawdown():
    print(f"=== 开始执行美股多策略分级监控 ===")
    alert_triggered = False

    # 工业级 Session 浏览器指纹伪装，彻底绕过雅虎财经对云端 IP 的反爬虫拦截，消灭 -nan%
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

            # 1. 动态抓取过去 30 个交易日的区间最高锚定点
            recent_high = df["High"].tail(30).max()
            
            # 2. 优先通过官方报价缓存捕获最新沉淀的价格
            current_price = stock.fast_info.get('lastPrice')
            
            # 3. 如果未开盘或非交易时段缓存为空，自动循环向前捕获有效收盘价兜底
            if current_price is None or math.isnan(current_price):
                for i in range(1, len(df) + 1):
                    price_check = df["Close"].iloc[-i]
                    if not math.isnan(price_check):
                        current_price = price_check
                        break
            
            if current_price is None or math.isnan(current_price):
                continue

            # 4. 计算当前真实的回调幅度
            drawdown = (recent_high - current_price) / recent_high * 100
            print(f"[{ticker}] {name}: 30日高点 ${recent_high:.2f} | 最新价 ${current_price:.2f} | 真实跌幅: -{drawdown:.2f}%")

            # 5. 触发个性化半凯利建仓区间
            if min_drop <= drawdown <= max_drop:
                alert_triggered = True
                
                # 量化计算：换算该笔风险资金应该购买的整股股数与具体金额
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
                    f"4. 动用资金: ${actual_spent:.2f} (严格符合半凯利风控)"
                )
                send_bark_notification(title, body)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产触及设定的加仓线，系统继续保持静默。")

if __name__ == "__main__":
    check_drawdown()
    
    # 6. 强制测试触发器：确保新 iPhone 绑定钥匙后能第一时间收到测试横幅
    print("--- 正在触发 Bark 苹果原生送达实验 ---")
    test_title = "📢【实操买入指令】测试：购买 纳指100-ETF(QQQ) 5股"
    test_body = (
        "iPhone Bark 实验成功！云端量化卫士完全打通。\n"
        "1. 动作: 买入 / BUY 🟢\n"
        "2. 代码: QQQ\n"
        "3. 数量: 5 股 (抗踏空底仓)\n"
        "4. 预计资金: $3,700.00\n\n"
        "今晚 21:30 开盘请手动在券商买入 VOO 6股和 QQQ 5股底仓，剩下的 75% 后备金静待本系统真实暴跌警报！"
    )
    send_bark_notification(test_title, test_body)
