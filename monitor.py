import os
import sys
from datetime import datetime
import requests
import yfinance as yf
import math

# ============================================================================
# ⚙️ 22大金刚黄金比例板块排他系统（对冲基金级终极完全体）
# ============================================================================
TOTAL_KELLY_BUDGET = 30000.0

# 🟢 概率学重构 1：根据华尔街黄金比例，为 6 大阵营死死锁定【单笔确切买入美元金额】
# 大盘重仓护盘、AI中重仓主攻、巨头稳健、黑马严格轻仓、医药与传统奶牛均衡对冲
GROUP_BUDGET_CONFIG = {
    "INDEX_大盘基金":  {"single_invest_usd": 4500.0},  # 大盘大坑，重兵砸入
    "AI_算力芯片":    {"single_invest_usd": 2250.0},  # AI算力，主攻冲锋
    "TECH_巨头生态":  {"single_invest_usd": 2000.0},  # 科技巨头，稳健白马
    "BLACK_弹性黑马":  {"single_invest_usd": 700.0},   # 高弹黑马，严格轻仓防风控
    "MED_生物医药":    {"single_invest_usd": 1300.0},  # 医药刚需，反向对冲
    "CASH_传统奶牛":  {"single_invest_usd": 1500.0}   # 实体奶牛，过路费收割
}

MONITOR_POOL = {
    # 1. 大盘基金阵营 (INDEX)
    "VOO":  {"name": "标普500-ETF", "group": "INDEX_大盘基金", "risk_factor": 1.0}, 
    "QQQ":  {"name": "纳指100-ETF", "group": "INDEX_大盘基金", "risk_factor": 1.0}, 
    # 2. AI算力与核心半导体 (AI_CHIP)
    "NVDA": {"name": "英伟达",     "group": "AI_算力芯片", "risk_factor": 1.8}, 
    "AVGO": {"name": "博通",       "group": "AI_算力芯片", "risk_factor": 1.6}, 
    # 3. 科技巨头闭环生态 (TECH_GIANT)
    "MSFT": {"name": "微软",       "group": "TECH_巨头生态", "risk_factor": 1.2}, 
    "AAPL": {"name": "苹果",       "group": "TECH_巨头生态", "risk_factor": 1.2},
    "GOOG": {"name": "谷歌-C",     "group": "TECH_巨头生态", "risk_factor": 1.3}, 
    "AMZN": {"name": "亚马逊",     "group": "TECH_巨头生态", "risk_factor": 1.4}, 
    "META": {"name": "Meta",       "group": "TECH_巨头生态", "risk_factor": 1.4}, 
    # 4. 高弹性黑马爆发卫星仓 (BLACK_HORSE)
    "TSLA": {"name": "特斯拉",     "group": "BLACK_弹性黑马", "risk_factor": 2.2},  
    "PLTR": {"name": "Palantir",   "group": "BLACK_弹性黑马", "risk_factor": 2.2},  
    "RKLB": {"name": "Rocket Lab", "group": "BLACK_弹性黑马", "risk_factor": 2.5},   
    # 5. 生物医药与医保垄断 (MEDICINE)
    "LLY":  {"name": "礼来",       "group": "MED_生物医药", "risk_factor": 1.4},  
    "NVO":  {"name": "诺和诺德",   "group": "MED_生物医药", "risk_factor": 1.4},
    "UNH":  {"name": "联合健康",   "group": "MED_生物医药", "risk_factor": 1.2},
    # 6. 线下传统消费、金融与数字收费公路 (CASH_COW)
    "COST": {"name": "Costco",     "group": "CASH_传统奶牛", "risk_factor": 1.1},  
    "WMT":  {"name": "沃尔玛",     "group": "CASH_传统奶牛", "risk_factor": 1.1},
    "V":    {"name": "Visa",       "group": "CASH_传统奶牛", "risk_factor": 1.2},
    "MA":   {"name": "万事达",     "group": "CASH_传统奶牛", "risk_factor": 1.2},
    "JPM":  {"name": "摩根大通",   "group": "CASH_传统奶牛", "risk_factor": 1.2},
    "CRM":  {"name": "Salesforce", "group": "CASH_传统奶牛", "risk_factor": 1.5},  
    "GE":   {"name": "通用电气",   "group": "CASH_传统奶牛", "risk_factor": 1.2}
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
    params = {"sound": "calypso", "group": group_name}
    try:
        requests.get(url, params=params)
        print(f"【Bark 高级网关】: 黄金比例自适应信号推送成功。")
    except Exception as e:
        print(f"发送 Bark 消息失败: {e}")

def run_integrated_sentinel():
    current_date = datetime.now()
    current_month = current_date.month
    current_day = current_date.day
    
    print(f"=== 运行22大金刚黄金比例行业排他网格系统 ({current_date.strftime('%Y-%m-%d %H:%M:%S')}) ===")
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})

    # 追踪当前扫描周期内，有哪些行业已经触发并被排他锁死
    triggered_groups = set()
    alert_triggered = False
    
    print("\n[实时扫描] 轨道一：3万美元22金刚黄金比例网格机制...")
    for ticker, config in MONITOR_POOL.items():
        name = config["name"]
        group_id = config["group"]
        risk_factor = config["risk_factor"]
        
        # 行业板块隔离排他锁死检查
        if group_id in triggered_groups:
            print(f"[{ticker}] {name}: -> 拦截原因: 该阵营【{group_id}】今日已发出购买指令，触发熔断排他机制，自动忽略本行。")
            continue
            
        try:
            stock = yf.Ticker(ticker, session=session)
            df = stock.history(period="60d")
            if df.empty or len(df) < 25:
                continue

            df['MA20'] = df['Close'].rolling(window=20).mean()
            ma20_current = df['MA20'].iloc[-1]

            recent_high = df["High"].tail(60).max()
            high_index = df["High"].tail(60).idxmax()
            days_since_high = len(df) - df.index.get_loc(high_index) - 1

            current_price = stock.fast_info.get('lastPrice') or df["Close"].iloc[-1]
            drawdown = (recent_high - current_price) / recent_high * 100

            # 贝叶斯波动率动态自适应调校
            df['High_Low'] = df['High'] - df['Low']
            df['ATR20'] = df['High_Low'].rolling(window=20).mean()
            atr_current = df['ATR20'].iloc[-1]
            volatility_pct = (atr_current / current_price) * 100
            
            smart_trigger_line = max(5.0, volatility_pct * risk_factor)
            print(f"[{ticker}] {name}: 60日高点 ${recent_high:.2f} | 现价 ${current_price:.2f} | 真实回撤: -{drawdown:.2f}% (自适应买入线: {smart_trigger_line:.2f}%)")

            if days_since_high <= 4:
                continue

            is_triggered = False
            strategy_type = ""
            
            # 【双档自动提盈收割引擎】
            if current_price >= ma20_current and (smart_trigger_line * 0.7) <= drawdown < smart_trigger_line:
                is_triggered = True
                strategy_type = "【🟢 趋势局部低吸】"
                
            elif current_price < ma20_current and drawdown >= smart_trigger_line:
                is_triggered = True
                strategy_type = "【🚨 深水长线抄底】"

            if is_triggered:
                alert_triggered = True
                # 🟢 板块熔断锁死生效
                triggered_groups.add(group_id)
                
                # 🟢 核心概率升级：自动提取当前阵营专属的科学黄金比例单笔买入美元金额
                invest_usd = GROUP_BUDGET_CONFIG[group_id]["single_invest_usd"]
                
                # 阶梯幂律放大因子：如果是大跌抄底档，允许资金自动放大1.2倍增强底部胜率
                if strategy_type == "【🚨 深水长线抄底】":
                    invest_usd = min(invest_usd * 1.3, invest_usd * (drawdown / smart_trigger_line))
                
                exact_shares = int(invest_usd // current_price)
                actual_spent = exact_shares * current_price
                if exact_shares == 0:
                    continue
                
                limit_price_standard = round(current_price * 0.996, 2)
                limit_price_extreme = round(current_price * 0.982, 2)
                
                title = f"📢{strategy_type} 购买 {name}({ticker}) {exact_shares}股"
                body = (
                    f"🎯 黄金比例行业排他策略成功捕获优质买点！\n"
                    f"所属阵营: 【{group_id}】(该阵营子弹已用完，系统已限时锁死防御)\n"
                    f"当前市价: ${current_price:.2f} (回撤 -{drawdown:.2f}%)\n\n"
                    f"--- \n"
                    f"⚙️ 确切实操挂单指引（限价单/Limit Order）：\n"
                    f"1. 建议成交数量: **{exact_shares} 股**\n"
                    f"2. 💡 常规买入参考限价: **`${limit_price_standard}`**\n"
                    f"3. 🔥 极限插针低吸价: **`${limit_price_extreme}`**\n\n"
                    f"📊 阵营科学预算调用: ${actual_spent:.2f}，资金流动性由底层自动过桥结算！"
                )
                send_bark_notification(title, body, group_name="3w黄金比例池")
                
        except Exception as e:
            print(f"扫描 {ticker} 失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产满足自适应网格买点，系统继续静默巡逻。")

    # ------------------------------------------------------------------------
    # 📈 轨道二：每月1万人民币 聪明定投仓核心逻辑
    # ------------------------------------------------------------------------
    print("\n[实时扫描] 轨道二：每月1万人民币聪明定投仓...")
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
                f"系统已为您捕捉到本月初最佳指数定投点！\n\n"
                + "\n\n".join(order_details) + "\n\n"
                f"⚙️ 操作指引：请现在打开券商App，直接使用上面给出的【确切挂单限价】下限价单。买入后本月定投结束！"
            )
            send_bark_notification(title, body, group_name="1w增量定投池")
        else:
            print(f" -> 提示: 今天（{current_day}号）大盘短线处于多头过热主升浪，未触及MA20均线回踩。定投继续保持静默。")

if __name__ == "__main__":
    run_integrated_sentinel()
