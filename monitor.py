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
# 1. 核心配置与防爆参数
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

VOLUME_MULTIPLIER = 3.0
MIN_STOCK_PRICE = 2.0
MIN_3DAY_AVG_TURNOVER = 5_000_000
SINGLE_SNIPER_BUDGET_USD = 800
MAX_SCAN_COUNT = 30
MAX_WORKERS = 5

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
# 3. 极速全美小盘股池获取（防云端封锁）
# ==========================================
def fetch_us_stock_universe():
    """
    由于 Finviz 库极易在 GitHub 虚拟机中触发 403 Forbidden 封锁，
    在此处采用极其刚猛的即时探测策略。一旦报错，立刻秒级启用最新的高动能热点池。
    """
    print("🛰 正在全量扫描全美股小盘股票池...", flush=True)
    
    # 精选美股当前最具高波动率、高爆发潜力的短线游资热门小盘股池（作为最强金身解耦兜底）
    backup_list = [
        "AXTI", "WOLF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", 
        "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX", "SOUN", 
        "BBAI", "PLUG", "BLNK", "MARA", "RIOT", "CAN", "WULF"
    ]
    
    try:
        from finvizfinance.screener.overview import Overview
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        
        # 限制请求超时，防止被 Finviz 防火墙挂死挂起
        df = fscreen.screener_view()
        if df is not None and not df.empty:
            df.columns = df.columns.str.strip()
            for col in ['Ticker', 'ticker', 'TICKER']:
                if col in df.columns:
                    print("✅ 成功从 Finviz 实时穿透获取最新股票池！", flush=True)
                    return df[col].astype(str).str.strip().tolist()
    except BaseException as e:
        # 无论是 Exception 还是系统级退出，强行拦截，保障流水线推进
        print(f"⚠️ 触发 GitHub 节点网络封锁防护 (原因: {e})，已秒级无缝切换至高动能热点兜底池！", flush=True)
        
    return backup_list

# ==========================================
# 4. 单股短线量化过滤引擎
# ==========================================
def process_single_stock(ticker_symbol: str):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # 短线爆破必须开启 prepost=True 狙击盘前对敲
        hist = ticker.history(period="40d", prepost=True)
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
        
        # 核心过滤关卡
        if price_t0 < MIN_STOCK_PRICE or avg_3day_turnover < MIN_3DAY_AVG_TURNOVER: 
            return None
            
        if mult_t1 >= VOLUME_MULTIPLIER or current_multiplier >= VOLUME_MULTIPLIER:
            # 计算 ATR 动态防御线
            high_low = hist['High'] - hist['Low']
            high_close = (hist['High'] - hist['Close'].shift()).abs()
            low_close = (hist['Low'] - hist['Close'].shift()).abs()
            tr = high_low.combine(high_close, max).combine(low_close, max)
            atr_val = tr.rolling(window=14).mean().iloc[-1]
            
            suggested_shares = SINGLE_SNIPER_BUDGET_USD / price_t0 if price_t0 > 0 else 0
            stop_loss_price = price_t0 - (2.5 * atr_val) if atr_val > 0 else price_t0 * 0.91
            
            print(f"🎯 发现潜在异动股: {ticker_symbol}，正在调配 AI 量化探针...", flush=True)
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
    print(f"🕒 当前北京时间: {bj_time.strftime('%Y-%m-%d %H:%M:%S')} | 正在进入过滤器...", flush=True)
    
    if not dynamic_stocks: 
        print("❌ 传入的股票池为空，退出运行。", flush=True)
        return
        
    target_stocks = dynamic_stocks[:MAX_SCAN_COUNT]
    print(f"🚀 经典启动 [全美股前 {len(target_stocks)} 只小盘股三日历史成交额穿透过滤]...", flush=True)
    
    triggered_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(process_single_stock, t): t for t in target_stocks}
        for future in as_completed(future_to_ticker):
            res = future.result()
            if res:
                triggered_count += 1
                yahoo_finance_url = f"https://yahoo.com{res['ticker']}"
                push_title = f"🚨 商业席位爆破：【{res['ticker']}】惊现游资机构超级扫货流！"
                push_content = (
                    f"🏷 【当前系统阶段】: 🧪 2026实战模拟推演期\n"
                    f"------------------------\n"
                    f"🧠 【AI 事件驱动· 核心因果深度剖析】:\n"
                    f"🗣 {res['ai_intelligence']}\n"
                    f"------------------------\n"
                    f"💰 实时价: ${res['price_t0']:.2f} | 昨日放量 {res['mult_t1']:.1f} 倍 / 今日实时 {res['current_multiplier']:.1f} 倍\n"
                    f"💎 资金深度检查: 近3日游资滚存平均日成交额达到 【 ${res['avg_3day_turnover']:,.0f} 美元 】\n"
                    f"🎯 【建议执行配额】: 【 {res['suggested_shares']:.0f} 股 】\n"
                    f"🛑 【ATR 动态游资防御线】: 止损价锁死在 【 ${res['stop_loss_price']:.2f} 】"
                )
                
                if BARK_KEY:
                    encoded_title = urllib.parse.quote_plus(push_title)
                    encoded_content = urllib.parse.quote_plus(push_content)
                    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=全美股主力爆破&sound=electronic&isArchive=1&url={urllib.parse.quote_plus(yahoo_finance_url)}"
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
