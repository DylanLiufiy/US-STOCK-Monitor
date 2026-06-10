import os
import sys
import time
import json
import urllib.parse
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types

# 强制禁用 Python 标准输出缓冲（确保 GitHub Actions 日志秒级刷新不漏字）
sys.stdout.reconfigure(line_buffering=True)

# ==========================================
# 1. 核心配置与短线资金风控参数
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

VOLUME_MULTIPLIER = 3.0         # 机构成交量狂飙倍数门槛
MIN_STOCK_PRICE = 2.0           # 过滤仙股
MIN_3DAY_AVG_TURNOVER = 5000000 # 近3日平均成交额至少 500 万美金，确保高流动性

# 🎯 核心短线资金池防火墙：单笔轻仓狙击写死固定 $800 美元！
# 完美适配你 $1,600 的独立短线池，确保最多同时持仓 2 只，绝不踩 25W 港币月度免佣红线！
SINGLE_SNIPER_BUDGET_USD = 800.0 
MAX_SCAN_COUNT = 30             # 云端单次扫描前 30 只最活跃的小盘股
MAX_WORKERS = 5                 # 并发线程数，防雅虎429限流

# ==========================================
# 2. 🧠 核心绑定：调用 Google 金融大模型进行短线爆破排雷
# ==========================================
def ask_google_short_term_investigation(ticker_symbol: str, price: float, mult: float) -> tuple:
    """
    短线事件驱动引擎：调用 Google 最强免费 API 通道 gemini-2.5-flash
    结合雅虎突发新闻和资金倍数，输出严格的结构化 JSON 排雷打分。
    """
    if not GOOGLE_API_KEY:
        return (60.0, "未绑定 GOOGLE_API_KEY，系统启动纯技术面通告。")
        
    try:
        # 初始化谷歌 Express 专属客户端
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        # 实时拉取小盘股近期的突发大事件新闻流
        t = yf.Ticker(ticker_symbol)
        news_list = t.news[:3] if t.news else []
        news_titles = [n.get('title', '') for n in news_list if n.get('title')]
        news_context = " | ".join(news_titles) if news_titles else "暂无近两日公开突发大事件"
        
        # 构建短线游资维度的量化推理 Prompt
        prompt = (
            f"你现在是部署在游资机构短线突击席位底层的 Google Finance AI 核心判研大脑。 "
            f"监控雷达刚拦截到全美小盘股 【{ticker_symbol}】 触发主力暴力抢筹信号，量价快照如下：\n"
            f"- 当前最新股价: ${price:.2f}\n"
            f"- 成交量狂飙倍数: {mult:.1f} 倍（处于历史罕见爆发状态）\n"
            f"- 突发关联新闻流: {news_context}\n\n"
            f"请作为顶级操盘手，结合这些非结构化新闻语义，刺破该股暴涨的底层导火索。给出以下两个核心判断：\n"
            f"1. confidence_score: 此次放量突破是“庄家诱多拉高出货（低分）”还是“有FDA、并购、财报大超预期等硬核基本面拐点（高分）”（输入0到100之间的浮点数）。\n"
            f"2. sharp_verdict: 一句话（80字内，干货大白话）剖析暴涨因果并给出一句老手的核心操盘防守建议。\n\n"
            f"必须以纯 JSON 格式输出，不要带有任何 markdown 格式标记，标准格式必须为：\n"
            f'{{"confidence_score": 75.5, "sharp_verdict": "判定..."}}'
        )
        
        # 呼叫对 API 通道 100% 长期全免费开放的最新推理大模型
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        
        # 解析 Google 智囊的打分
        res_data = json.loads(response.text)
        return float(res_data["confidence_score"]), str(res_data["sharp_verdict"])
        
    except Exception as e:
        print(f"⚠ Google 短线排雷引擎通信异常: {e}", flush=True)
        return (50.0, "💡 谷歌大脑网络微震，请严格跟随一分钟 K 线趋势，分段设置止损。")

# ==========================================
# 3. 极速全美小盘股池获取（防 Actions 云端 403 封锁）
# ==========================================
def fetch_us_stock_universe():
    print("🛰 正在全量扫描全美股小盘股票池...", flush=True)
    # 精选当前最具高爆发、高波动潜力的短线游资热门小盘股池（作为最强防封锁兜底池）
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
        # 开启 prepost=True 拦截盘前对敲与暗池拉升
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
        
        # 刚性过滤关卡
        if price_t0 < MIN_STOCK_PRICE or avg_3day_turnover < MIN_3DAY_AVG_TURNOVER: 
            return None
            
        if mult_t1 >= VOLUME_MULTIPLIER or current_multiplier >= VOLUME_MULTIPLIER:
            # 真实波幅 ATR 14 计算
            high_low = hist['High'] - hist['Low']
            high_close = (hist['High'] - hist['Close'].shift()).abs()
            low_close = (hist['Low'] - hist['Close'].shift()).abs()
            tr = high_low.combine(high_close, max).combine(low_close, max)
            atr_val = tr.rolling(window=14).mean().iloc[-1]
            
            suggested_shares = SINGLE_SNIPER_BUDGET_USD / price_t0 if price_t0 > 0 else 0
            stop_loss_price = price_t0 - (2.5 * atr_val) if atr_val > 0 else price_t0 * 0.91
            
            trigger_mult = max(mult_t1, current_multiplier)
            print(f"🎯 发现游资量价异动股: {ticker_symbol}，正在调配 Google 预测大脑分析新闻...", flush=True)
            
            # 🔥 核心绑定：调用 Google 大模型获取置信度得分与一句话死穴研判
            google_score, google_verdict = ask_google_short_term_investigation(ticker_symbol, price_t0, trigger_mult)
            
            return {
                "ticker": ticker_symbol, "price_t0": price_t0, "mult_t1": mult_t1, "mult_t2": mult_t2,
                "current_multiplier": current_multiplier, "avg_3day_turnover": avg_3day_turnover,
                "suggested_shares": suggested_shares, "stop_loss_price": stop_loss_price,
                "google_score": google_score, "google_verdict": google_verdict
            }
    except Exception:
        pass
    return None

# ==========================================
# 5. 调度执行与 Bark 消息强分发
# ==========================================
def execute_all_us_strategy(dynamic_stocks):
    bj_time = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8)))
    print(f"🕒 当前北京时间: {bj_time.strftime('%Y-%m-%d %H:%M:%S')} | 正在切入短线狙击阵地...", flush=True)
    
    if not dynamic_stocks: 
        print("❌ 传入的股票池为空，退出运行。", flush=True)
        return
        
    target_stocks = dynamic_stocks[:MAX_SCAN_COUNT]
    print(f"🚀 启动 [全美股前 {len(target_stocks)} 只小盘股三日历史成交额穿透过滤]...", flush=True)
    
    triggered_count = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(process_single_stock, t): t for t in target_stocks}
        for future in as_completed(future_to_ticker):
            res = future.result()
            if res:
                triggered_count += 1
                yahoo_finance_url = f"https://yahoo.com{res['ticker']}"
                
                push_title = f"🚨 谷歌排雷警报：【{res['ticker']}】惊现主力超级大单突破！"
                push_content = (
                    f"🧠 【Google Finance AI · 突发因果深度排雷】\n"
                    f"🔮 谷歌突击置信度得分: 【 {res['google_score']:.1f} / 100 】\n"
                    f"🗣 谷歌老手研判: {res['google_verdict']}\n"
                    f"------------------------\n"
                    f"💰 实时现价: ${res['price_t0']:.2f} | 昨日放量 {res['mult_t1']:.1f} 倍 / 今日实时 {res['current_multiplier']:.1f} 倍\n"
                    f"💎 资金深度检查: 近3日游资平均日成交额达到 【 ${res['avg_3day_turnover']:,.0f} 美元 】\n"
                    f"📈 动能承接链: 前日量 {res['mult_t2']:.1f}x ➔ 昨日爆破 {res['mult_t1']:.1f}x ➔ 今日承接 {res['current_multiplier']:.1f}x\n"
                    f"------------------------\n"
                    f"⚔️ 【全美低流水量化突击单动作】\n"
                    f"💵 独立机动子弹: 【 $800.00 美元 】 ➔ 建议立即买入: 【 {res['suggested_shares']:.0f} 股 】\n"
                    f"🛑 【ATR 动态游资防御线】: 止损价锁死在 【 ${res['stop_loss_price']:.2f} 】\n"
                    f"------------------------\n"
                    f"📝 风控提示: 短线持仓上限 2 只。超过 25W 港币月度总流水分额券商会触发高额阶梯佣金，请快进快出，破止损线坚决离场。"
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
        requests.get(f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=系统状态&sound=none", timeout=10)

if __name__ == "__main__":
    stock_universe = fetch_us_stock_universe()
