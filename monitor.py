import os
import sys
from datetime import datetime
import requests
import yfinance as yf
import math

# 1. 配置你的总预算（3万美元本金）
TOTAL_BUDGET = 30000.0

# 2. 极致安全监控池：指数维持5%，个股拉高到12%以上、黑马15%以上起步
MONITOR_POOL = {
    "VOO":  {"name": "标普500-ETF", "min": 5.0,  "max": 10.0, "risk_pct": 20.0}, 
    "QQQ":  {"name": "纳指100-ETF", "min": 5.0,  "max": 10.0, "risk_pct": 20.0}, 
    "NVDA": {"name": "英伟达",     "min": 12.0, "max": 22.0, "risk_pct": 10.0}, 
    "MSFT": {"name": "微软",       "min": 10.0, "max": 18.0, "risk_pct": 10.0}, 
    "GOOG": {"name": "谷歌-C",     "min": 10.0, "max": 18.0, "risk_pct": 10.0}, 
    "PLTR": {"name": "Palantir",   "min": 15.0, "max": 25.0, "risk_pct": 8.0}   
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
    params = {"sound": "bell", "group": "美股凯利监控"}
    try:
        requests.get(url, params=params)
        print(f"【Bark 苹果原生网关响应】: 发送成功")
    except Exception as e:
        print(f"发送 Bark 独立消息失败: {e}")

def check_drawdown():
    print(f"=== 开始执行牛市过滤防御版美股监控 ===")
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
            df = stock.history(period="60d") # 抓取60天历史K线
            if df.empty or len(df) < 20:
                continue

            # 🟢 战术升级 1：计算20日简单移动平均线 (MA20)，判断多头趋势
            df['MA20'] = df['Close'].rolling(window=20).mean()
            ma20_current = df['MA20'].iloc[-1]

            # 拿到近60个交易日的最高价及其发生的位置（索引位置）
            recent_high = df["High"].tail(60).max()
            high_index = df["High"].tail(60).idxmax()
            
            # 计算最高点距离今天过去了多少个交易日
            days_since_high = len(df) - df.index.get_loc(high_index) - 1

            # 优先通过官方报价缓存捕获最新价格
            current_price = stock.fast_info.get('lastPrice')
            if current_price is None or math.isnan(current_price):
                for i in range(1, len(df) + 1):
                    price_check = df["Close"].iloc[-i]
                    if not math.isnan(price_check):
                        current_price = price_check
                        break
            
            if current_price is None or math.isnan(current_price):
                continue

            # 计算真实回调幅度
            drawdown = (recent_high - current_price) / recent_high * 100
            
            print(f"[{ticker}] {name}: 60日高点 ${recent_high:.2f}(距今{days_since_high}天) | 最新价 ${current_price:.2f} | MA20线 ${ma20_current:.2f} | 相对回撤: -{drawdown:.2f}%")

            # 🟢 战术升级 2：核心创新高多头趋势过滤逻辑
            # 防火墙 A: 如果最高点是在最近 5 个交易日内创出的，判定为多头创新高强势状态，绝不报警！
            if days_since_high <= 5:
                print(f"    -> 过滤原因: {name} 最近5天内刚创过历史新高，属于主升浪，继续保持静默。")
                continue
                
            # 防火墙 B: 如果最新价格依然牢牢站在 20日均线 (MA20) 上方，说明趋势没破，只是牛市正常震荡，不叫砸坑！
            if current_price >= ma20_current:
                print(f"    -> 过滤原因: {name} 股价仍站在20日均线上方，多头大趋势未破，无需加仓。")
                continue

            # 只有同时通过两道多头防火墙，且跌幅真正破线，才判定为“长线黄金砸坑期”
            if min_drop <= drawdown <= max_drop:
                alert_triggered = True
                target_cash_amount = TOTAL_BUDGET * (risk_pct / 100.0)
                exact_shares = int(target_cash_amount // current_price)
                actual_spent = exact_shares * current_price
                
                if exact_shares == 0:
                    continue
                    
                title = f"📢【实操买入指令】购买 {name}({ticker}) {exact_shares}股"
                body = (
                    f"触发中长线【{min_drop}%~{max_drop}%】深度趋势洗盘抄底点。\n"
                    f"最新价: ${current_price:.2f} (已真正跌破20日均线，且从高点回撤 -{drawdown:.2f}%)\n"
                    f"1. 动作: 买入 / BUY 🟢\n"
                    f"2. 代码: {ticker}\n"
                    f"3. 数量: {exact_shares} 股\n"
                    f"4. 动用资金: ${actual_spent:.2f}"
                )
                send_bark_notification(title, body)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何核心资产触及中长线加仓线，系统继续保持静默。")

if __name__ == "__main__":
    check_drawdown()
