import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
import yfinance as yf

# 强制禁用 Python 标准输出缓冲（确保 GitHub 日志实时刷新）
sys.stdout.reconfigure(line_buffering=True)

# ==========================================
# 1. 核心配置与短线风控参数
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

VOLUME_MULTIPLIER = 3.0         # 成交量狂飙倍数门槛
MIN_STOCK_PRICE = 2.0           # 过滤垃圾仙股
MIN_3DAY_AVG_TURNOVER = 5000000 # 近3日平均成交额至少 500 万美金，确保高流动性防止踩坑

# 🎯 核心资金防火墙：单笔轻仓狙击刚好 $800，完美适配您 $1600 的独立短线池（最多同时持仓 2 只）
SINGLE_SNIPER_BUDGET_USD = 800.0 
MAX_SCAN_COUNT = 30             # 云端单次扫描前 30 只活跃股
MAX_WORKERS = 5                 # 并发线程数，防雅虎429限流

# ==========================================
# 2. 智能化 AI 分析引擎
# ==========================================
def ask_ai_investigation(ticker_symbol: str, price: float, mult: float) -> str:
    if not DEEPSEEK_API_KEY:
        return "ℹ 未配置 AI 情绪钥匙，系统启动纯技术面拦截通告。"
    try:
        t = yf.Ticker(ticker_symbol)
        news_list = t.news[:3] if t.news else []
        news_titles = [n.get('title', '') for n in news_list if n.get('title')]
        news_context = " | ".join(news_titles) if news_titles else "暂无近两日公开突发大事件"
        
        prompt = (
            f"作为美股顶级游资席位量化主管，请用一句话（100字内，干货大白话）刺破美股小盘股【{ticker_symbol}】"
            f"突然触发机构暴力抢筹（股价${price:.2f}，成交量狂飙{mult:.1f} 倍）的底层导火索。"
            f"结合最新的新闻流：{news_context}。告诉老手这是主力拉高出货、还是有重大基本面拐点，并给出一句核心行动策略。"
        )
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        response = requests.post(
            "https://deepseek.com", 
            json=data, 
            headers=headers, 
            timeout=10
        )
        if response.status_code == 200:
            return response.json()['choices']['message']['content'].strip()
    except Exception as e:
        print(f"⚠ AI 短线爆破分析异常: {e}", flush=True)
    return "💡 [系统提示] 游资席位异动剧烈，请严格跟随一分钟K线趋势，止损定死。"

# ==========================================
# 3. 极速全美小盘股池获取（防云端封锁解耦）
# ==========================================
def fetch_us_stock_universe():
    print("🛰 正在全量扫描全美股小盘股票池...", flush=True)
    # 精选美股高动能、高爆发潜力的短线游资热门小盘股池（作为防 GitHub Action 403 的最强刚性兜底池）
    backup_list = [
        "AXTI", "WOLF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", 
        "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX", "SOUN", 
        "BBAI", "PLUG", "BLNK", "MARA", "RIOT", "CAN", "WULF"
    ]
    try:
        from finvizfinance.screener.overview import Overview
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        df = fscreen.screener_view()
        if df is not None and not df.empty:
            df.columns = df.columns.str.strip()
            for col in ['Ticker', 'ticker', 'TICKER']:
                if col in df.columns:
                    print("✅ 成功从 Finviz 实时穿透获取最新股票池！", flush=True)
                    return df[col].astype(str).str.strip().tolist()
    except BaseException as e:
        print(f"⚠️ 触发 GitHub 节点网络封锁防护 (原因: {e})，已秒级无缝切换至高动能热点兜底池！", flush=True)
    return backup_list

# ==========================================
# 4. 单股短线量化过滤引擎
# ==========================================
def process_single_stock(ticker_symbol: str):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="40d", prepost=True) # 开启 prepost 狙击暗池对敲
        if hist.empty or len(hist) < 32: 
            return None
            
        hist = hist.dropna(subset=['Close', 'Volume'])
        past_30_days_volume = hist['Volume'].iloc[-32:-2]
        avg_volume_30d = past_30_days_volume.mean()
        if avg_volume_30d <= 0: 
            return None
            
        price_t0, vol_t0 = float(hist['Close'].iloc[-1]), float(hist['Volume'].iloc[-1])
        price_t1, vol_t1 = float(hist['Close'].iloc[-2]), float(hist['Volume'].iloc[-2])
        price_t2, vol_t2 = float(hist['Close'].iloc[-3]), float(hist['Volume'].iloc[-3])
        
        avg_3day_turnover = ((price_t0 * vol_t0) + (price_t1 * vol_t1) + (price_t2 * vol_t2)) / 3
        
        current_multiplier = vol_t0 / avg_volume_30d
        mult_t1 = vol_t1 / avg_volume_30d
        mult_t2 = vol_t2 / avg_volume_30d
        
        # 核心过滤关卡（包含高流动性额度过滤，贴合 25W 港币总池流水风控）
        if price_t0 < MIN_STOCK_PRICE or avg_3day_turnover < MIN_3DAY_AVG_TURNOVER: 
            return None
            
        if mult_t1 >= VOLUME_MULTIPLIER or current_multiplier >= VOLUME_MULTIPLIER:
            # 计算 ATR 14 真实波幅动态防御线
            high_low = hist['High'] - hist['Low']
            high_close = (hist['High'] - hist['Close'].shift()).abs()
            low_close = (hist['Low'] - hist['Close'].shift()).abs()
            tr = high_low.combine(high_close, max).combine(low_close, max)
            atr_val = tr.rolling(window=14).mean().iloc[-1]
            
            suggested_shares = SINGLE_SNIPER_BUDGET_USD / price_t0 if price_t0 > 0 else 0
            stop_loss_price = price_t0 - (2.5 * atr_val) if atr_val > 0 else price_t0 * 0.91
            
            print(f"🎯 发现异动股: {ticker_symbol}，正在调配 AI 量化探针...", flush=True)
            ai_intelligence = ask_ai_investigation(ticker_symbol, price_t0, max(mult_t1, current_multiplier))
            
            return {
                "ticker": ticker_symbol, "price_t0": price_t0, "mult_t1": mult_t1, "mult_t2": mult_t2,
                "current_multiplier": current_multiplier, "avg_3day_turnover": avg_3day_turnover,
                "suggested_shares": suggested_shares, "stop_loss_price": stop_loss_price,
                "ai_intelligence": ai_intelligence
            }
    except Exception:
        pass
    return None

# ==========================================
# 5. 调度执行主策略
# ==========================================
def execute_all_us_strategy(dynamic_stocks):
    bj_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    print(f"🕒 当前北京时间: {bj_time.strftime('%Y-%m-%d %H:%M:%S')} | 进入短线雷达...", flush=True)
    
    if not dynamic_stocks: return
    target_stocks = dynamic_stocks[:MAX_SCAN_COUNT]
    
    triggered_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(process_single_stock, t): t for t in target_stocks}
        for future in as_completed(future_to_ticker):
            res = future.result()
            if res:
                triggered_count += 1
                yahoo_finance_url = f"https://yahoo.com{res['ticker']}"
                push_title = f"🚨 短线突击警报：【{res['ticker']}】惊现主力暴力扫货流！"
                push_content = (
                    f"🏷 【当前系统阶段】: 🧪 2026实战模拟推演期\n"
                    f"------------------------\n"
                    f"🧠 【AI 事件驱动· 核心因果深度剖析】:\n"
                    f"🗣 {res['ai_intelligence']}\n"
                    f"------------------------\n"
                    f"💰 实时价: ${res['price_t0']:.2f} | 昨日放量 {res['mult_t1']:.1f} 倍 / 今日实时 {res['current_multiplier']:.1f} 倍\n"
                    f"💎 资金深度检查: 近3日平均日成交额达到 【 ${res['avg_3day_turnover']:,.0f} 美元 】\n"
                    f"⚔️ 独立突击子弹: 【 $800.00 美元 】 ➔ 建议立即买入: 【 {res['suggested_shares']:.0f} 股 】\n"
                    f"🛑 【ATR 动态游资防御线】: 止损价锁死在 【 ${res['stop_loss_price']:.2f} 】\n"
                    f"------------------------\n"
                    f"📝 风控提示: 短线持仓上限 2 只。超过 25W 港币月度总流水分额券商会触发高额佣金，请快进快出，破止损线坚决离场。"
                )
                
                if BARK_KEY:
                    encoded_title = urllib.parse.quote_plus(push_title)
                    encoded_content = urllib.parse.quote_plus(push_content)
                    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=短线狙击黑马&sound=electronic&isArchive=1&url={urllib.parse.quote_plus(yahoo_finance_url)}"
                    requests.get(url, timeout=10)
                time.sleep(1.0)
                
    if triggered_count == 0 and BARK_KEY:
        encoded_title = urllib.parse.quote_plus("🟢 短线爆破雷达：安全站岗中")
        encoded_content = urllib.parse.quote_plus("全美股大数据穿透扫描结束。今日高流动性标的未发生机构暗池突发爆量。游资线无风险。")
        requests.get(f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group=系统状态&sound=none", timeout=10)

if __name__ == "__main__":
    stock_universe = fetch_us_stock_universe()
    execute_all_us_strategy(stock_universe)
    print("🏁 全美股大数据三日量价实时穿透扫描全部结束。", flush=True)
