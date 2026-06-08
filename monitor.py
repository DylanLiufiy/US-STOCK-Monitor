import os
import sys
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import polars as pl
import yfinance as yf

# ==============================================================================
# ❄️ 56只全行业立体对冲【北京工作时间专属型】生存系统 (V5.1 补全执行体)
# ==============================================================================

# 读取全局 Secrets 中的 Bark 密钥
BARK_KEY = os.environ.get("BARK_URL", "请在GitHub_Secrets中配置BARK_URL")

LEDGER_FILE = "portfolio_ledger_v5.json"
INITIAL_BUDGET = 30000.0   
MAX_DRAWDOWN_LIMIT = 5.0   

TRADE25_MONTHLY_FREE_LIMIT_HKD = 250000.0   
USD_TO_HKD_FX_RATE = 7.8                    

# 56只精选全行业前沿标的多因子分类矩阵
STRATEGY_PORTFOLIO_CONFIG = {
    "CORE_STABLE": {
        "name": "安全底座层", "single_invest_usd": 1500.0, 
        "tickers": ["SPY", "QQQ", "NVDA", "AVGO", "MSFT", "LLY", "NVO", "WM", "KO"]
    },
    "AGGRESSIVE_GROWTH": {
        "name": "略微激进层", "single_invest_usd": 1000.0, 
        "tickers": ["GE", "EMR", "ROK", "HON", "RTX", "LMT", "CEG", "VST", "NEE", "COIN", "HOOD", "PYPL"]
    },
    "DARK_HORSE": {
        "name": "强黑马层", "single_black_horse_cap": 450.0, 
        "tickers": ["PLTR", "PATH", "BBAI", "SOUN", "EH", "JOBY", "ACHR", "RKLB", "IONQ", "RGTI", "CRSP", "NTLA", "DNA", "ARWR"]
    }
}

HEDGE_INSTRUMENT = "SQQQ"   
ALL_TICKERS = [t for layer in STRATEGY_PORTFOLIO_CONFIG.values() for t in layer["tickers"]] + [HEDGE_INSTRUMENT, "SPY"]
ALL_TICKERS = list(set(ALL_TICKERS))


def load_ledger_v5():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {
        "cash": INITIAL_BUDGET, "holdings": {}, "history_trades": [], "daily_net_worth_history": [], 
        "spy_benchmark_shares": None, "circuit_breaker_active": False, "spy_above_sma20_days": 0, 
        "pushed_news_ids": [], "trade25_used_hkd": 0.0, "last_reset_month": datetime.now().strftime("%Y-%m")
    }

def save_ledger_v5(ledger):
    with open(LEDGER_FILE, 'w', encoding='utf-8') as f: json.dump(ledger, f, indent=4, ensure_ascii=False)


def check_spy_health_via_polars(market_data, ledger):
    try:
        if "SPY" in market_data and not market_data["SPY"].empty: spy_pd = market_data["SPY"]
        else: spy_pd = yf.download("SPY", period="60d", progress=False)
        spy_prices = spy_pd['Close'].dropna().tolist()
        pl_df = pl.DataFrame({"close": spy_prices})
        pl_df = pl_df.with_columns(pl.col("close").rolling_mean(window=20).alias("sma20"))
        spy_current = pl_df["close"][-1]
        spy_sma20 = pl_df["sma20"][-1]
        if spy_current > spy_sma20: ledger["spy_above_sma20_days"] = ledger.get("spy_above_sma20_days", 0) + 1
        else: ledger["spy_above_sma20_days"] = 0
        return spy_current, spy_sma20, ledger["spy_above_sma20_days"]
    except Exception as e:
        print(f"Polars大盘趋势解算异常: {e}", file=sys.stderr)
        return 0.0, 0.0, 0


def extract_advanced_keywords(title):
    t_lower = title.lower()
    kws = []
    if "ai" in t_lower or "robot" in t_lower or "automation" in t_lower: kws.append("物理AI/智能")
    if "drone" in t_lower or "evtol" in t_lower: kws.append("无人机低空")
    if "space" in t_lower or "rocket" in t_lower or "launch" in t_lower: kws.append("商业航天")
    if "beats" in t_lower or "earnings" in t_lower: kws.append("财报异动")
    if "upgrade" in t_lower or "raised" in t_lower: kws.append("评级上调")
    if "downgrade" in t_lower or "lowered" in t_lower: kws.append("评级下调")
    if not kws: kws.append("权威财经")
    return kws


def analyze_news_with_time_decay(news_item, ledger):
    title = news_item.get('title', '')
    summary = news_item.get('summary', '') or news_item.get('text', '')
    pub_time_raw = news_item.get('providerPublishTime') or news_item.get('pubDate')
    if not title: return "NEUTRAL"
    if pub_time_raw:
        try:
            pub_datetime = datetime.fromtimestamp(pub_time_raw) if isinstance(pub_time_raw, (int, float)) else datetime.strptime(pub_time_raw, '%Y-%m-%dT%H:%M:%SZ')
            if datetime.now() - pub_datetime > timedelta(hours=48): return "NEUTRAL" 
        except: pass
    text = (title + " " + summary).lower()
    if any(w in text for w in ["upgrade", "beats", "surpasses", "buy", "growth", "contract", "raised"]): return "BULL"
    if any(w in text for w in ["downgrade", "misses", "investigation", "lawsuit", "drop", "plunge", "cuts"]): return "BEAR"
    return "NEUTRAL"


def trigger_tail_risk_hedging(ledger, market_data):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    high_beta_tickers = ["QQQ", "NVDA"]
    cash_reclaimed = 0.0
    for ticker in high_beta_tickers:
        if ticker in ledger["holdings"]:
            hold_info = ledger["holdings"][ticker]
            shares_to_sell = round(hold_info["shares"] * 0.3, 4)
            if shares_to_sell > 0:
                try:
                    price = float(market_data.get(ticker)['Close'].iloc[-1])
                    cash_reclaimed += (shares_to_sell * price)
                    hold_info["shares"] = round(hold_info["shares"] - shares_to_sell, 4)
                    if hold_info["shares"] <= 0: ledger["holdings"].pop(ticker)
                    ledger["history_trades"].append({"date": now_str, "ticker": ticker, "type": "HEDGE_REDUCE", "shares": shares_to_sell, "price": price})
                except: pass
    if cash_reclaimed > 0:
        try:
            hedge_price = float(market_data.get(HEDGE_INSTRUMENT)['Close'].iloc[-1])
            hedge_shares = round(cash_reclaimed / hedge_price, 4)
            if HEDGE_INSTRUMENT in ledger["holdings"]: ledger["holdings"][HEDGE_INSTRUMENT]["shares"] = round(ledger["holdings"][HEDGE_INSTRUMENT]["shares"] + hedge_shares, 4)
            else: ledger["holdings"][HEDGE_INSTRUMENT] = {"shares": hedge_shares, "entry_price": hedge_price}
            ledger["history_trades"].append({"date": now_str, "ticker": HEDGE_INSTRUMENT, "type": "HEDGE_BUY", "shares": hedge_shares, "price": hedge_price})
        except: ledger["cash"] += cash_reclaimed


def release_tail_risk_hedging(ledger, market_data):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if HEDGE_INSTRUMENT in ledger["holdings"]:
        try:
            hedge_info = ledger["holdings"].pop(HEDGE_INSTRUMENT)
            price = float(market_data.get(HEDGE_INSTRUMENT)['Close'].iloc[-1])
            reclaimed_cash = hedge_info["shares"] * price
            ledger["cash"] += reclaimed_cash
            ledger["history_trades"].append({"date": now_str, "ticker": HEDGE_INSTRUMENT, "type": "HEDGE_LIQUIDATE", "shares": hedge_info["shares"], "price": price})
        except: pass


def fetch_news_worker(ticker):
    try: return ticker, yf.Ticker(ticker).news
    except: return ticker, []


# ------------------------------------------------------------------------------
# 📬 补全底层执行层：完美适配 Https/纯Key/带斜杠格式的 Bark 推送核心
# ------------------------------------------------------------------------------
def execute_bark_push(title, content, force_alert=False):
    if not BARK_KEY or "请在" in BARK_KEY:
        print("❌ 穿透风控提示：未在全局 Secret 环境变量中发现可用的 BARK_URL。")
        return
        
    raw_key = BARK_KEY.strip()
    base_url = raw_key.rstrip('/') if raw_key.startswith("http") else f"https://day.app{raw_key}"
    
    payload = {
        "title": title,
        "body": content,
        "group": "美股工作时间流",
        "icon": "https://unsplash.com",
        "isArchive": 1
    }
    if force_alert: payload["sound"] = "calypso"
        
    try:
        res = requests.post(base_url, data=payload, timeout=12)
        if res.status_code == 200: print("🚀 【推送成功】高价值金融头条已击穿苹果 APNS 送达手机！")
        else: print(f"❌ Bark服务器中转故障，状态码: {res.status_code}")
    except Exception as e:
        print(f"❌ 穿透网关超时，可能是本地或云端虚拟机网络发生异常抖动: {e}")


def run_advanced_survivor_pipeline():
    ledger = load_ledger_v5()
    now_dt = datetime.now()
    now_str = now_dt.strftime('%Y-%m-%d')
    
    # 🕵️‍♂️ 【判断是否为主动运行】：如果非北京工作时间，但在终端手动输入运行，将强制打通所有通知
    # 对应北京时间 09:00 - 18:00 为云端服务器 UTC 的 01:00 到 10:00
    is_beijing_working_hours = 1 <= now_dt.hour <= 10
    
    # 获取虚拟机运行的系统环境变量（如果是 GitHub 手动点击触发，GITHUB_EVENT_NAME 会是 'workflow_dispatch'）
    is_manual_trigger = os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" or not os.environ.get("GITHUB_ACTIONS")
    
    try:
        market_data = yf.download(ALL_TICKERS, period="60d", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"数据总线故障: {e}")
        return

    spy_price, spy_sma20, consecutive_days = check_spy_health_via_polars(market_data, ledger)
    
    current_stock_value = 0.0
    for ticker, info in ledger["holdings"].items():
        try: current_stock_value += info["shares"] * float(market_data.get(ticker)['Close'].iloc[-1])
        except: current_stock_value += info["shares"] * info["entry_price"]
        
    total_net_worth = ledger["cash"] + current_stock_value
    
    history_nw = [x["net_worth"] for x in ledger["daily_net_worth_history"]]
    peak_worth = max(history_nw) if history_nw else INITIAL_BUDGET
    if total_net_worth > peak_worth: peak_worth = total_net_worth
    current_drawdown = ((peak_worth - total_net_worth) / peak_worth) * 100 if total_net_worth < peak_worth else 0.0

    status_str = "🟢 策略运行稳健，账户处于安全增值期"
    force_alert = False 
    
    if current_drawdown >= MAX_DRAWDOWN_LIMIT and not ledger["circuit_breaker_active"]:
        ledger["circuit_breaker_active"] = True
        trigger_tail_risk_hedging(ledger, market_data)
        status_str = "🚨 触发 5% 回撤防御熔断！已自动执行【高Beta持仓减产 30% 并买入 SQQQ 对冲防护】！"
        force_alert = True 
    elif ledger["circuit_breaker_active"]:
        if current_drawdown < MAX_DRAWDOWN_LIMIT and consecutive_days >= 2:
            ledger["circuit_breaker_active"] = False
            release_tail_risk_hedging(ledger, market_data)
