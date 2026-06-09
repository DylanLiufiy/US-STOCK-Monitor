import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf
from finvizfinance.screener.overview import Overview

BARK_KEY = os.environ.get("BARK_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

VOLUME_MULTIPLIER = 3.0       
MIN_STOCK_PRICE = 2.0         
MIN_3DAY_AVG_TURNOVER = 5_000_000 
SINGLE_SNIPER_BUDGET_USD = 800  
MAX_SCAN_COUNT = 45             

def ask_ai_investigation(ticker_symbol: str, price: float, mult: float) -> str:
    """🧠 商业级 AI 事件驱动引擎：起底小盘股主力扫货内幕"""
    if not DEEPSEEK_API_KEY:
        return "ℹ 未配置 AI 情绪钥匙，系统启动纯技术面拦截通告。"
    try:
        t = yf.Ticker(ticker_symbol)
        news_list = t.news[:3]
        news_titles = [n.get('title', '') for n in news_list if n.get('title')]
        news_context = " | ".join(news_titles) if news_titles else "暂无近两日公开突发大事件"
        
        prompt = (
            f"作为美股顶级游资席位量化主管，请用一句话（100字内，干货大白话）刺破美股小盘股【{ticker_symbol}】"
            f"突然触发机构暴力抢筹（股价${price:.2f}，成交量狂飙{mult:.1f}倍）的底层导火索。"
            f"结合最新的新闻流：{news_context}。告诉老手这是主力拉高出货、还是有重大基本面拐点（如FDA、并购、财报超预期），"
            f"并给出一句核心行动策略。"
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
        response = requests.post("https://deepseek.com", json=data, headers=headers, timeout=12)
        if response.status_code == 200:
            return response.json()['choices']['message']['content'].strip()
    except Exception as e:
        print(f"⚠ AI 短线爆破情绪分析异常: {e}")
    return "💡 [系统提示] 游资席位异动剧烈，请严格跟随一分钟K线趋势，止损定死。"

def fetch_us_stock_universe():
    print("🛰 正在全量扫描全美股数千家挂牌公司...")
    backup_list = ["AXTI", "WOLF", "XFABF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX"]
    try:
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        try:
            df = fscreen.get_screener_platform(layout='Overview')
        except AttributeError:
            df = fscreen.screener_view()
            
        if df is not None and not df.empty:
            df.columns = df.columns.str.strip()
            ticker_col = None
            for col in ['Ticker', 'ticker', 'TICKER']:
                if col in df.columns:
                    ticker_col = col; break
            if ticker_col:
                return df[ticker_col].astype(str).str.strip().tolist()
        return backup_list
    except Exception as e:
        return backup_list

def execute_all_us_strategy(dynamic_stocks):
    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    
    if not (8 <= bj_hour < 22): return
    if not dynamic_stocks: return

    target_stocks = dynamic_stocks[:MAX_SCAN_COUNT]
    print(f"🚀 经典启动 [全美股前 {len(target_stocks)} 只小盘股三日历史成交额穿透过滤]...")
    triggered_count = 0

    for ticker_symbol in target_stocks:
        try:
            ticker = yf.Ticker(ticker_symbol)
            # ✨ 亮点提升：短线爆破同样强行注入 prepost=True。让游资在盘前对敲、拉升的量能无处遁形
            hist = ticker.history(period="40d", prepost=True).dropna(subset=['Close', 'Volume'])
            if len(hist) < 31: continue

            past_30_days_volume = hist['Volume'].iloc[-32:-2]
            avg_volume_30d = past_30_days_volume.mean()
            if avg_volume_30d <= 0: continue

            price_t0 = float(hist['Close'].iloc[-1]) 
            vol_t0 = float(hist['Volume'].iloc[-1])
            price_t1 = float(hist['Close'].iloc[-2]) 
            vol_t1 = float(hist['Volume'].iloc[-2])
            price_t2 = float(hist['Close'].iloc[-3]) 
            vol_t2 = float(hist['Volume'].iloc[-3])

            turnover_t0 = price_t0 * vol_t0
            turnover_t1 = price_t1 * vol_t1
            turnover_t2 = price_t2 * vol_t2
            avg_3day_turnover = (turnover_t0 + turnover_t1 + turnover_t2) / 3

            mult_t1 = vol_t1 / avg_volume_30d
            mult_t2 = vol_t2 / avg_volume_30d
            current_multiplier = vol_t0 / avg_volume_30d 

            if price_t0 < MIN_STOCK_PRICE: continue
            if avg_3day_turnover < MIN_3DAY_AVG_TURNOVER: continue

            if mult_t1 >= VOLUME_MULTIPLIER or current_multiplier >= VOLUME_MULTIPLIER:
                high_low = hist['High'] - hist['Low']
                high_close = (hist['High'] - hist['Close'].shift()).abs()
                low_close = (hist['Low'] - hist['Close'].shift()).abs()
                tr = high_low.combine(high_close, max).combine(low_close, max)
                atr_val = tr.rolling(window=14).mean().iloc[-1]

                suggested_shares = SINGLE_SNIPER_BUDGET_USD / price_t0 if price_t0 > 0 else 0
                stop_loss_price = price_t0 - (2.5 * atr_val) if atr_val > 0 else price_t0 * 0.91

                trigger_mult = max(mult_t1, current_multiplier)
                print(f"🤖 正在调配 AI 量化探针...")
                ai_intelligence = ask_ai_investigation(ticker_symbol, price_t0, trigger_mult)

                yahoo_finance_url = f"https://yahoo.com{ticker_symbol}"
                triggered_count += 1

                push_title = f"🚨 商业席位爆破：【{ticker_symbol}】惊现游资机构超级扫货流！"
                push_content = (
                    f"🏷 【当前系统阶段】: 🧪 2026实战模拟推演期\n"
                    f"------------------------\n"
                    f"🧠 【AI 事件驱动·核心因果深度剖析】:\n"
                    f"🗣 {ai_intelligence}\n"
                    f"------------------------\n"
                    f"💰 实时价: ${price_t0:.2f} (包含盘前盘后深度追踪) | 昨日放量 {mult_t1:.1f} 倍 / 今日实时 {current_multiplier:.1f} 倍\n"
                    f"💎 资金深度检查: 近3日游资滚存平均日成交额达到 【 ${avg_3day_turnover:,.0f} 美元 】\n"
                    f"📈 动能连贯性: 前日量 {mult_t2:.1f}x ➔ 昨日爆破 {mult_t1:.1f}x ➔ 今日承接 {current_multiplier:.1f}x\n"
                    f"🎯 【全美高流动性量化突击单】:\n"
                    f"💵 拨发轻仓突击子弹: 【 $800 美元 】 ➔ 建议执行配额: 【 {suggested_shares:.0f} 股 】\n"
                    f"🛑 【ATR 动态游资防御线】: 止损价精准锁死在 【 ${stop_loss_price:.2f} 】(包含盘前最高最低价测算)\n"
                    f"------------------------\n"
                    f"📝 提示: 手机端点击此卡片可直接一步唤醒雅虎财经看盘。"
                )
                encoded_title = urllib.parse.quote_plus(push_title)
                encoded_content = urllib.parse.quote_plus(push_content)
                url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=全美股主力爆破&sound=electronic&isArchive=1&url={urllib.parse.quote_plus(yahoo_finance_url)}"
                if BARK_KEY: requests.get(url, timeout=15)
                time.sleep(2.0) 
        except Exception: continue

    if triggered_count == 0:
        encoded_title = urllib.parse.quote_plus("🟢 短线爆破雷达：安全站岗中")
        encoded_content = urllib.parse.quote_plus(f"全美股大数据穿透扫描结束（包含盘前全量穿透）。今日高流动性标的未发生机构暗池突发爆量。游资线无风险。")
        url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=系统状态&sound=none&isArchive=1"
        if BARK_KEY: requests.get(url, timeout=10)

if __name__ == "__main__":
    stock_universe = fetch_us_stock_universe()
    execute_all_us_strategy(stock_universe)
    print("🏁 全美股大数据三日量价实时穿透扫描全部结束。")
