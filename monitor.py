import os
import sys
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import polars as pl
import yfinance as yf

# ==============================================================================
# ❄️ 56只全行业立体对冲【GitHub Actions 云端专用】生存系统 (V5 最终生产体)
# ==============================================================================

# 🔑 【安全升级】：彻底移除明文 Key，直接安全读取你在 GitHub 全局 Secrets 里填写的 BARK_URL
BARK_KEY = os.environ.get("BARK_URL", "请在GitHub_Secrets中配置BARK_URL")

LEDGER_FILE = "portfolio_ledger_v5.json"
INITIAL_BUDGET = 30000.0   
MAX_DRAWDOWN_LIMIT = 5.0   

# Trade25 专属政策参数
TRADE25_MONTHLY_FREE_LIMIT_HKD = 250000.0   # 每月 25 万港币免佣金上限
USD_TO_HKD_FX_RATE = 7.8                    # 美元兑港币固定汇率
POST_FREE_MIN_COMMISSION_USD = 1.99         # 额度用完后，单笔买卖最低惩罚性佣金

# 56只全行业标的多因子分类矩阵
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

HEDGE_INSTRUMENT = "SQQQ"   # 🛡️ 尾部反向对冲基金
ALL_TICKERS = [t for layer in STRATEGY_PORTFOLIO_CONFIG.values() for t in layer["tickers"]] + [HEDGE_INSTRUMENT, "SPY"]
ALL_TICKERS = list(set(ALL_TICKERS))


def load_ledger_v5():
    """读取账本，自动执行跨月额度重置"""
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
            ledger = json.load(f)
            current_month = datetime.now().strftime("%Y-%m")
            if ledger.get("last_reset_month", "") != current_month:
                ledger["trade25_used_hkd"] = 0.0
                ledger["last_reset_month"] = current_month
                print(f"📅 监测到新月份 {current_month}，系统自动重置 Trade25 免佣额度。")
            return ledger
    return {
        "cash": INITIAL_BUDGET, "holdings": {}, "history_trades": [], "daily_net_worth_history": [], 
        "spy_benchmark_shares": None, "circuit_breaker_active": False, "spy_above_sma20_days": 0, 
        "pushed_news_ids": [], "trade25_used_hkd": 0.0, "last_reset_month": datetime.now().strftime("%Y-%m")
    }

def save_ledger_v5(ledger):
    with open(LEDGER_FILE, 'w', encoding='utf-8') as f:
        json.dump(ledger, f, indent=4, ensure_ascii=False)


def check_spy_health_via_polars(market_data, ledger):
    """【Polars 向量加速引擎】：多线程底层解算大盘 SMA20，彻底告别单线程阻塞"""
    try:
        if "SPY" in market_data and not market_data["SPY"].empty:
            spy_pd = market_data["SPY"]
        else:
            spy_pd = yf.download("SPY", period="60d", progress=False)
            
        spy_prices = spy_pd['Close'].dropna().tolist()
        pl_df = pl.DataFrame({"close": spy_prices})
        pl_df = pl_df.with_columns(pl.col("close").rolling_mean(window=20).alias("sma20"))
        
        spy_current = pl_df["close"][-1]
        spy_sma20 = pl_df["sma20"][-1]
        
        if spy_current > spy_sma20:
            ledger["spy_above_sma20_days"] = ledger.get("spy_above_sma20_days", 0) + 1
        else:
            ledger["spy_above_sma20_days"] = 0
            
        return spy_current, spy_sma20, ledger["spy_above_sma20_days"]
    except Exception as e:
        print(f"Polars计算大盘趋势异常: {e}", file=sys.stderr)
        return 0.0, 0.0, 0


def analyze_news_with_time_decay(news_item, ledger):
    """【48小时情绪半衰期过滤器】：强制剔除过期旧闻，防范庄家利用历史利好诱多"""
    title = news_item.get('title', '')
    summary = news_item.get('summary', '') or news_item.get('text', '')
    pub_time_raw = news_item.get('providerPublishTime') or news_item.get('pubDate')
    
    if not title: return "NEUTRAL"
    
    if pub_time_raw:
        try:
            pub_datetime = datetime.fromtimestamp(pub_time_raw) if isinstance(pub_time_raw, (int, float)) else datetime.strptime(pub_time_raw, '%Y-%m-%dT%H:%M:%SZ')
            if datetime.now() - pub_datetime > timedelta(hours=48):
                return "NEUTRAL" 
        except:
            pass
            
    text = (title + " " + summary).lower()
    if any(w in text for w in ["upgrade", "beats", "surpasses", "buy", "growth", "contract", "raised"]): return "BULL"
    if any(w in text for w in ["downgrade", "misses", "investigation", "lawsuit", "drop", "plunge", "cuts"]): return "BEAR"
    return "NEUTRAL"


def trigger_tail_risk_hedging(ledger, market_data):
    """【主动型对冲锁机制】：跌破 5% 最大回撤时，自动执行高 Beta 股票减产 30%，并将现金直接倾注于 SQQQ 锁死下行亏损"""
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
            if HEDGE_INSTRUMENT in ledger["holdings"]:
                ledger["holdings"][HEDGE_INSTRUMENT]["shares"] = round(ledger["holdings"][HEDGE_INSTRUMENT]["shares"] + hedge_shares, 4)
            else:
                ledger["holdings"][HEDGE_INSTRUMENT] = {"shares": hedge_shares, "entry_price": hedge_price}
            ledger["history_trades"].append({"date": now_str, "ticker": HEDGE_INSTRUMENT, "type": "HEDGE_BUY", "shares": hedge_shares, "price": hedge_price})
        except:
            ledger["cash"] += cash_reclaimed


def release_tail_risk_hedging(ledger, market_data):
    """【智能解封对冲】：大盘重新站稳 SMA20 连续 2 天后，自动清仓 SQQQ 变现，恢复全行业进攻仓位"""
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

def run_advanced_survivor_pipeline():
    """【GitHub Actions 专用运行逻辑】：每次单向触发盘点，并将变化持久化写入本地 JSON"""
    ledger = load_ledger_v5()
    now_dt = datetime.now()
    now_str = now_dt.strftime('%Y-%m-%d')
    
    # 🔒 【防打扰升级】：判断当前运行时间是否处于北京时间的深夜睡觉时段
    # GitHub Actions 服务器强制采用 UTC 时间。
    # 北京时间 23:00 - 次日 05:00 映射到 UTC 时间为 15:00 - 21:00
    is_sleep_time = 15 <= now_dt.hour <= 21
    
    try:
        # 16线程并发洗刷全盘 56 只股票K线数据
        market_data = yf.download(ALL_TICKERS, period="60d", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"数据拉取失败: {e}")
        return

    # 调用 Polars 向量引擎解算大盘均线状态
    spy_price, spy_sma20, consecutive_days = check_spy_health_via_polars(market_data, ledger)
    
    # 统计资产总市值
    current_stock_value = 0.0
    for ticker, info in ledger["holdings"].items():
        try: current_stock_value += info["shares"] * float(market_data.get(ticker)['Close'].iloc[-1])
        except: current_stock_value += info["shares"] * info["entry_price"]
        
    total_net_worth = ledger["cash"] + current_stock_value
    
    # trailing 最大回撤风控状态机判定
    history_nw = [x["net_worth"] for x in ledger["daily_net_worth_history"]]
    peak_worth = max(history_nw) if history_nw else INITIAL_BUDGET
    if total_net_worth > peak_worth: peak_worth = total_net_worth
    current_drawdown = ((peak_worth - total_net_worth) / peak_worth) * 100 if total_net_worth < peak_worth else 0.0

    status_str = "🟢 策略运行稳健，账户处于安全增值期"
    force_alert = False # 标志位：是否强制打破静默发出高危风险警报
    
    if current_drawdown >= MAX_DRAWDOWN_LIMIT and not ledger["circuit_breaker_active"]:
        ledger["circuit_breaker_active"] = True
        trigger_tail_risk_hedging(ledger, market_data)
        status_str = "🚨 触发 5% 回撤防御熔断！已自动执行【高Beta持仓减产 30% 并买入 SQQQ 对冲防护】！"
        force_alert = True # 触及生死线，必须强震动唤醒
    elif ledger["circuit_breaker_active"]:
        if current_drawdown < MAX_DRAWDOWN_LIMIT and consecutive_days >= 2:
            ledger["circuit_breaker_active"] = False
            release_tail_risk_hedging(ledger, market_data)
            status_str = f"🎉 右侧拐点确认！大盘已连续 {consecutive_days} 天收于20日线之上。对冲功成身退，全线恢复交易权限。"
            force_alert = True
        else:
            status_str = f"🔒 熔断锁保持。大盘 SPY 连续站稳进度: {consecutive_days}/2 天。SQQQ 对冲头寸在场护盘中。"

    # 48小时高活性新闻过滤抓取
    new_bulls, new_bears = [], []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(fetch_news_worker, t) for t in ALL_TICKERS if t not in ["SPY", HEDGE_INSTRUMENT]]
        for fut in as_completed(futures):
            t, t_news = fut.result()
            if not t_news: continue
            for item in t_news[:2]:
                nid = item.get('uuid') or item.get('id')
                if not nid or nid in ledger.get("pushed_news_ids", []): continue
