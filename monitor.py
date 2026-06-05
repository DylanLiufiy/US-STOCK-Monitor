import os
import sys
from datetime import datetime
import requests
import yfinance as yf
import math

# ============================================================================
# ⚙️ 资金与策略池核心配置
# ============================================================================
TOTAL_KELLY_BUDGET = 30000.0
KELLY_POOL = {
    "VOO":  {"name": "标普500-ETF", "min": 5.0,  "max": 10.0, "risk_pct": 20.0}, 
    "QQQ":  {"name": "纳指100-ETF", "min": 5.0,  "max": 10.0, "risk_pct": 20.0}, 
    "NVDA": {"name": "英伟达",     "min": 12.0, "max": 22.0, "risk_pct": 10.0}, 
    "MSFT": {"name": "微软",       "min": 10.0, "max": 18.0, "risk_pct": 10.0}, 
    "GOOG": {"name": "谷歌-C",     "min": 10.0, "max": 18.0, "risk_pct": 10.0}, 
    "AVGO": {"name": "博通",       "min": 12.0, "max": 22.0, "risk_pct": 10.0}, 
    "TSLA": {"name": "特斯拉",     "min": 12.0, "max": 22.0, "risk_pct": 8.0},  
    "CRM":  {"name": "Salesforce", "min": 10.0, "max": 18.0, "risk_pct": 8.0},  
    "LLY":  {"name": "礼来",       "min": 10.0, "max": 18.0, "risk_pct": 8.0},  
    "PLTR": {"name": "Palantir",   "min": 15.0, "max": 25.0, "risk_pct": 8.0},  
    "RKLB": {"name": "Rocket Lab", "min": 15.0, "max": 25.0, "risk_pct": 5.0}   
}

FIXED_定投_BUDGET = 1400.0
定投_TICKERS = ["VOO", "QQQ"]

BARK_URL = os.environ.get("BARK_URL")

def send_bark_notification(title, body, group_name="美股核心量化"):
    if not BARK_URL:
        print(f"未配置 BARK_URL，取消发送")
        return
    base_url = BARK_URL if BARK_URL.endswith("/") else BARK_URL + "/"
    encoded_title = requests.utils.quote(title)
    encoded_body = requests.utils.quote(body)
    url = f"{base_url}{encoded_title}/{encoded_body}"
    params = {"sound": "bell", "group": group_name}
    try:
        requests.get(url, params=params)
        print(f"【Bark 原生网关】: 推送成功")
    except Exception as e:
        print(f"发送 Bark 消息失败: {e}")

def run_integrated_sentinel():
    current_date = datetime.now()
    current_month = current_date.month
    current_day = current_date.day
    
    print(f"=== 开始执行美股全景二合一双轨监控 ({current_date.strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

    # ------------------------------------------------------------------------
    # 🏹 轨道一：3万美元 凯利深水鱼雷仓（加入自适应挂单限价计算）
    # ------------------------------------------------------------------------
    print("\n[正在扫描] 轨道一：3万美元凯利深水鱼雷仓...")
    for ticker, config in KELLY_POOL.items():
        name = config["name"]
        min_drop = config["min"]
        max_drop = config["max"]
        risk_pct = config["risk_pct"]
        
        try:
            stock = yf.Ticker(ticker, session=session)
            df = stock.history(period="60d")
            if df.empty or len(df) < 20:
                continue

            df['MA20'] = df['Close'].rolling(window=20).mean()
            ma20_current = df['MA20'].iloc[-1]

            recent_high = df["High"].tail(60).max()
            high_index = df["High"].tail(60).idxmax()
            days_since_high = len(df) - df.index.get_loc(high_index) - 1

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
            print(f"[{ticker}] {name}: 60日高点 ${recent_high:.2f}(距今{days_since_high}天) | 最新价 ${current_price:.2f} | MA20 ${ma20_current:.2f} | 相对回撤: -{drawdown:.2f}%")

            # 牛市创新高与20日多头趋势过滤
            if days_since_high <= 5 or current_price >= ma20_current:
                continue

            if min_drop <= drawdown <= max_drop:
                target_cash_amount = TOTAL_KELLY_BUDGET * (risk_pct / 100.0)
                exact_shares = int(target_cash_amount // current_price)
                actual_spent = exact_shares * current_price
                if exact_shares == 0:
                    continue
                
                # 🟢 核心限价算法：算出两档确切的券商限价单挂单建议
                limit_price_standard = round(current_price * 0.995, 2)  # 下浮 0.5% 作为常规买入安全限价
                limit_price_extreme = round(current_price * 0.980, 2)   # 下浮 2.0% 作为盘中黄金插针极限价
                    
                title = f"📢【凯利狙击指令】购买 {name}({ticker}) {exact_shares}股"
                body = (
                    f"⚠️ 触发 3万美元 现金池深度黄金抄底点。\n"
                    f"当前最新价: ${current_price:.2f} (自60日高位已回撤 -{drawdown:.2f}%)\n\n"
                    f"--- \n"
                    f"⚙️ 确切实操挂单指引（请去券商App下 限价单/Limit Order）：\n"
                    f"1. 稳健成交数量: **{exact_shares} 股**\n"
                    f"2. 💡 常规参考挂单限价: **`${limit_price_standard}`** (安全垫0.5%, 盘中震荡极易成交)\n"
                    f"3. 🔥 极限防守插针价: **`${limit_price_extreme}`** (深水下浮2%, 捕捉盘中瞬间大暴砸)\n\n"
                    f"📊 预计占用资金: ${actual_spent:.2f}，请合理安排现金储备！"
                )
                send_bark_notification(title, body, group_name="3w凯利深水池")
        except Exception as e:
            print(f"扫描 {ticker} 失败: {e}")

    # ------------------------------------------------------------------------
    # 📈 轨道二：每月1万人民币 聪明定投仓逻辑（同样注入限价保护机制）
    # ------------------------------------------------------------------------
    print("\n[正在扫描] 轨道二：每月1万人民币聪明定投仓...")
    
    if current_month < 7:
        print(f" -> 提示: 当前是 {current_month} 月。按照约定，1w人民币聪明定投逻辑在 7 月 1 日前保持静默。")
        return

    if 1 <= current_day <= 7:
        should_buy_fixed_today = False
        is_force_day = (current_day >= 7)
        order_details = []

        for ticker in 定投_TICKERS:
            try:
                stock = yf.Ticker(ticker, session=session)
                df = stock.history(period="30d")
                if df.empty or len(df) < 20:
                    continue

                df['MA20'] = df['Close'].rolling(window=20).mean()
                ma20 = df['MA20'].iloc[-1]
                current_price = stock.fast_info.get('lastPrice') or df["Close"].iloc[-1]
                bias = (current_price - ma20) / ma20 * 100

                fund_budget = FIXED_定投_BUDGET / 2.0
                exact_shares = int(fund_budget // current_price)
                
                # 定投安全挂单限价（同样下浮0.5%防止高位滑点）
                smart_limit_price = round(current_price * 0.995, 2)
                
                name = "标普500-ETF" if ticker == "VOO" else "纳指100-ETF"
                order_details.append(
                    f"🔍 {name}({ticker}): 现价 ${current_price:.2f}\n"
                    f"   👉 实操建议：下限价单买入 **{exact_shares}股** | 确切挂单限价: **`${smart_limit_price}`**"
                )

                if bias <= 0.5 or is_force_day:
                    should_buy_fixed_today = True
            except Exception as e:
                print(f"计算定投 {ticker} 出错: {e}")

        if should_buy_fixed_today:
            action_type = "【🚨 月初强制保底定投】" if is_force_day else "【🟢 月初智能定投指令】"
            title = f"{action_type} 执行 {current_month} 月固定定投"
            body = (
                f"系统已为您捕捉到本月初最佳指数定投切入点！\n\n"
                + "\n\n".join(order_details) + "\n\n"
                f"⚙️ 操作指引：请现在打开券商App，直接使用上面给出的【确切挂单限价】下限价单。买入后本月定投结束！"
            )
            send_bark_notification(title, body, group_name="1w增量定投池")
        else:
            print(f" -> 提示: 今天（{current_day}号）大盘短线处于多头过热主升浪，未触及均线回踩。定投继续保持静默。")

if __name__ == "__main__":
    run_integrated_sentinel()
