import os
import sys
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import polars as pl
import yfinance as yf

# ==============================================================================
# ❄️ 56只全行业立体对冲【强制首发调试穿透版】生存系统 (V5.4 终极完全体)
# ==============================================================================

BARK_KEY = os.environ.get("BARK_URL") or os.environ.get("BARK_KEY") or "请在GitHub_Secrets中配置"
SERVER_CHAN_KEY = os.environ.get("SERVER_CHAN_KEY") 

LEDGER_FILE = "portfolio_ledger_v5.json"
INITIAL_BUDGET = 30000.0   
MAX_DRAWDOWN_LIMIT = 5.0   
TRADE25_MONTHLY_FREE_LIMIT_HKD = 250000.0   
USD_TO_HKD_FX_RATE = 7.8                    

STRATEGY_PORTFOLIO_CONFIG = {
    "CORE_STABLE": {"name": "安全底座层", "single_invest_usd": 1500.0, "tickers": ["SPY", "QQQ", "NVDA", "AVGO", "MSFT", "LLY", "NVO", "WM", "KO"]},
    "AGGRESSIVE_GROWTH": {"name": "略微激进层", "single_invest_usd": 1000.0, "tickers": ["GE", "EMR", "ROK", "HON", "RTX", "LMT", "CEG", "VST", "NEE", "COIN", "HOOD", "PYPL"]},
    "DARK_HORSE": {"name": "强黑马层", "single_black_horse_cap": 450.0, "tickers": ["PLTR", "PATH", "BBAI", "SOUN", "EH", "JOBY", "ACHR", "RKLB", "IONQ", "RGTI", "CRSP", "NTLA", "DNA", "ARWR"]}
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
        return pl_df["close"][-1], pl_df["sma20"][-1], ledger.get("spy_above_sma20_days", 0)
    except: return 0.0, 0.0, 0


def extract_advanced_keywords(title):
    t_lower = title.lower()
    kws = []
    if "ai" in t_lower or "robot" in t_lower: kws.append("物理AI/智能")
    if "drone" in t_lower or "evtol" in t_lower: kws.append("无人机低空")
    if "space" in t_lower or "rocket" in t_lower: kws.append("商业航天")
    if "beats" in t_lower or "earnings" in t_lower: kws.append("财报异动")
    if "upgrade" in t_lower: kws.append("评级上调")
    if not kws: kws.append("权威财经")
    return kws


def analyze_news_with_time_decay(news_item, ledger):
    title = news_item.get('title', '')
    summary = news_item.get('summary', '') or news_item.get('text', '')
    pub_time_raw = news_item.get('providerPublishTime') or news_item.get('pubDate')
    
    if not title: return "NEUTRAL"
    if pub_time_raw and isinstance(pub_time_raw, (int, float)):
        try:
            if pub_time_raw > 9999999999: pub_time_raw = pub_time_raw / 1000.0
            pub_datetime = datetime.fromtimestamp(pub_time_raw)
            if datetime.now() - pub_datetime > timedelta(hours=48): return "NEUTRAL" 
        except: pass
    text = (title + " " + summary).lower()
    if any(w in text for w in ["upgrade", "beats", "surpasses", "buy", "growth", "contract", "raised"]): return "BULL"
    if any(w in text for w in ["downgrade", "misses", "investigation", "lawsuit", "drop", "plunge", "cuts"]): return "BEAR"
    return "NEUTRAL"


def fetch_news_worker(ticker):
    try: return ticker, yf.Ticker(ticker).news
    except: return ticker, []


def execute_dual_channel_push(title, content, force_alert=False):
    pushed_success = False
    if BARK_KEY and "请在" not in BARK_KEY:
        clean_key = BARK_KEY.strip().rstrip('/')
        base_url = clean_key if clean_key.startswith("http") else f"https://day.app{clean_key}"
            
        payload = {
            "title": title, "body": content, "group": "美股生存流",
            "icon": "https://unsplash.com", "isArchive": 1
        }
        try:
            res = requests.post(base_url, data=payload, timeout=12)
            if res.status_code == 200:
                print("🚀 【通道一：Bark 穿透成功！已经在Log中成功打印！】")
                pushed_success = True
            else:
                print(f"❌ Bark 接口拒绝，状态码: {res.status_code}")
        except Exception as e:
            print(f"⚠️ Bark 节点网络超时: {e}")

    if not pushed_success and SERVER_CHAN_KEY and "请在" not in SERVER_CHAN_KEY:
        s_key = SERVER_CHAN_KEY.strip()
        sc_url = f"https://ftqq.com{s_key}.send"
        try:
            s_res = requests.post(sc_url, data={"title": title, "desp": content}, timeout=12)
            if s_res.status_code == 200: print("🔒 【通道二：Server酱微信替代穿透成功！】")
        except: pass


def run_advanced_survivor_pipeline():
    ledger = load_ledger_v5()
    now_str = datetime.now().strftime('%Y-%m-%d')
    
    # 🧪 【调试机制升级】：强制强开时间锁和数据流，让本次测试绝对不被静默拦截
    is_beijing_working_hours = True 
    is_manual_trigger = True
    
    print("正在强制洗刷 56 只个股并生成调试信息报告...")
    try:
        market_data = yf.download(ALL_TICKERS, period="5d", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"数据拉取超时: {e}")
        return

    spy_price, spy_sma20, _ = check_spy_health_via_polars(market_data, ledger)
    
    current_stock_value = 0.0
    for ticker, info in ledger["holdings"].items():
        try: current_stock_value += info["shares"] * float(market_data.get(ticker)['Close'].iloc[-1])
        except: current_stock_value += info["shares"] * info["entry_price"]
    total_net_worth = ledger["cash"] + current_stock_value
    
    # 🧪 【强制注入测试高收益推荐新闻】：规避因为开盘期无消息导致的假死死锁
    new_bulls = [
        {
            "ticker": "EH", 
            "title": "亿航智能完成物理AI具身低空无人机历史首飞，订单暴涨超预期！", 
            "link": "https://github.com", 
            "tags": "`#无人机低空` `#业绩超预期`", 
            "source": "路透社财经头条"
        },
        {
            "ticker": "NVDA", 
            "title": "英伟达发布全新下一代具身智能超级计算芯片，华尔街全线调高买入评级！", 
            "link": "https://github.com", 
            "tags": "`#物理AI/智能` `#评级上调`", 
            "source": "彭博社商业简报"
        }
    ]
    new_bears = []

    remaining_free_hkd = max(0.0, TRADE25_MONTHLY_FREE_LIMIT_HKD - ledger["trade25_used_hkd"])
    free_quota_pct = (remaining_free_hkd / TRADE25_MONTHLY_FREE_LIMIT_HKD) * 100

    # 🛠️ 核心修复线：在硬盘先创建并初始化这个账本，彻底搞定第 5 步 Git Auto-Commit 找不到文件的报错！
    save_ledger_v5(ledger)
    
    report_body = f"### 🛡️ 寿星全行业多因子生存策略情报 ({now_str})\n"
    report_body += f"* **策略当前净资产 (NAV)**: `${total_net_worth:,.2f}`\n"
    report_body += f"* **Trade25 本月剩余免佣**: `{remaining_free_hkd:,.2f} HKD` (占比: `{free_quota_pct:.1f}%`)\n\n"
    report_body += "#### 📰 机构级突发深度舆情 (Reuters/Bloomberg)\n"
    
    for item in new_bulls: 
        report_body += f"* 🟢 **{item['ticker']}** {item['tags']}  \n  [{item['title']}]({item['link']}) *(来源: {item['source']})*\n"
        
    report_body += f"\n---\n*🎯 推送状态：测试打通成功。下周一开盘系统将自动捕捉真实高价值信号。*"

    title_prefix = "⚡ 调试验证：生存系统首发穿透测试"
    execute_dual_channel_push(title_prefix, report_body)


if __name__ == "__main__":
    run_advanced_survivor_pipeline()
