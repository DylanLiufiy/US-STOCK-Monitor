import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf

# ==================== 🏛 商业级长线核心配置区域 ====================
BARK_KEY = os.environ.get("BARK_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY") 

VIX_ANCHOR = "^VIX"
SECTOR_ANCHOR = "SOXX"

INTELLIGENT_ETFS = ["VOO", "QQQ"]
LONG_TERM_STOCKS = ["GOOG"] 

ROE_THRESHOLD = 0.15
PE_MAX_THRESHOLD = 35
RSI_BUY_LINE = 35
LONG_TERM_FLEXIBLE_RESERVE = 20000
# ==================================================================

def ask_ai_investigation(ticker_symbol: str, current_price: float, current_rsi: float) -> str:
    """🧠 商业级 AI 事件驱动引擎：秒级拆解大资金建仓背后的深层原因"""
    if not DEEPSEEK_API_KEY:
        return "ℹ 未配置 AI 情绪钥匙，系统启动纯技术面拦截通告。"
    try:
        t = yf.Ticker(ticker_symbol)
        news_list = t.news[:3]
        news_titles = [n.get('title', '') for n in news_list if n.get('title')]
        news_context = " | ".join(news_titles) if news_titles else "暂无近两日突发重大公告"
        
        prompt = (
            f"作为资深华尔街量化策略师，请用一句话（100字内，极简大白话）犀利拆解美股【{ticker_symbol}】"
            f"当前技术面触发黄金坑买入信号（股价${current_price:.2f}，RSI为{current_rsi:.1f}）的底层催化剂。"
            f"请结合其最新突发新闻线索：{news_context}。告诉散户这是机构恶意诱空还是真金白银的产业利好，"
            f"并给出一句核心行动建议。"
        )
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
        response = requests.post("https://deepseek.com", json=data, headers=headers, timeout=12)
        if response.status_code == 200:
            return response.json()['choices']['message']['content'].strip()
    except Exception as e:
        print(f"⚠ AI 新闻情绪引擎分析发生异常: {e}")
    return "💡 [系统提示] 盘面突发异动，技术面共振进入左侧加仓区，请密切关注今晚财报披露或美联储纪要。"

def calculate_rsi_and_atr(df, period=14):
    """计算精准指标"""
    if len(df) < period + 1: return 50, 0.0
    deltas = df['Close'].diff().dropna()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.ewm(com=period-1, min_periods=period).mean()
    avg_loss = losses.ewm(com=period-1, min_periods=period).mean()
    rsi = 100 if float(avg_loss.iloc[-1]) == 0 else (100 - (100 / (1 + rs))).iloc[-1]
    
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = high_low.combine(high_close, max).combine(low_close, max)
    atr = tr.rolling(window=period).mean().iloc[-1]
    return rsi, float(atr)

def process_stock_signal(ticker_symbol: str, is_etf: bool, current_vix: float, sector_rsi: float, vix_strategy: str, current_flexible_spend: float, status_label: str):
    try:
        ticker = yf.Ticker(ticker_symbol)
        if not is_etf:
            try:
                info = ticker.info
                roe = info.get("returnOnEquity", 0)
                pe = info.get("trailingPE", 0)
                peg = info.get("pegRatio", 1.0)
                if roe is None or roe < ROE_THRESHOLD: return False
                if pe is None or pe > PE_MAX_THRESHOLD or pe <= 0: return False
                if peg is not None and peg > 1.5: return False
            except Exception: return False

        # ✨ 亮点提升：开启 prepost=True 强行穿透并捕获盘前盘后的真实量价轨迹，杜绝信号滞后
        hist = ticker.history(period="250d", prepost=True).dropna(subset=['Close']) 
        if len(hist) < 210: return False

        current_price = float(hist['Close'].iloc[-1])
        ma200 = float(hist['Close'].rolling(window=200).mean().iloc[-1])
        current_rsi, atr_val = calculate_rsi_and_atr(hist)
        is_stock_above_ma200 = current_price > ma200

        if is_stock_above_ma200 and (current_rsi <= RSI_BUY_LINE or sector_rsi <= 35):
            suggested_shares = current_flexible_spend / current_price if current_price > 0 else 0
            stop_loss_price = current_price - (2.5 * atr_val) if atr_val > 0 else current_price * 0.93

            print(f"🤖 正在调用 AI 情绪控制中枢...")
            ai_intelligence = ask_ai_investigation(ticker_symbol, current_price, current_rsi)
            yahoo_finance_url = f"https://yahoo.com{ticker_symbol}"

            push_title = f"💎 商业价值发现：【{ticker_symbol}】触及量化左侧加仓点！"
            push_content = (
                f"🏷 【当前系统阶段】: {status_label}\n"
                f"🧐 实时 VIX 恐慌指数: {current_vix:.2f} | 行业 RSI: {sector_rsi:.1f}\n"
                f"🗺 宏观流动性大局观: {vix_strategy}\n"
                f"------------------------\n"
                f"🧠 【AI 事件驱动深度因果剖析】:\n"
                f"🗣 {ai_intelligence}\n"
                f"------------------------\n"
                f"💰 实时价: ${current_price:.2f} (包含盘前盘后追踪，稳守MA200生命线 ${ma200:.2f} 上方)\n"
                f"🚨 【储备金加码精准跟单】:\n"
                f"💵 本次分配子弹: 【 ${current_flexible_spend:,.0f} 美元 】\n"
                f"🛒 建议模拟买入股数: 【 {suggested_shares:.0f} 股 】\n"
                f"🛑 【ATR 动态波幅防线】: 止损价设为 【 ${stop_loss_price:.2f} 】(已根据个股盘前+日内波幅动态调整)\n"
                f"------------------------\n"
                f"📅 【每月发薪日正规军强制纪律单】:\n"
                f"💵 工资分配: 发薪后 $1,400 新资金请分别对半 700 美元买入 VOO 与 QQQ 底仓！"
            )
            encoded_title = urllib.parse.quote_plus(push_title)
            encoded_content = urllib.parse.quote_plus(push_content)
            url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=灵活资金加码雷达&sound=calypso&isArchive=1&url={urllib.parse.quote_plus(yahoo_finance_url)}"
            if BARK_KEY: requests.get(url, timeout=10)
            time.sleep(1.5)
            return True 
    except Exception as e:
        print(f"❌ 处理 {ticker_symbol} 异常: {e}")
    return False

def execute_combined_diagnosis():
    current_date = datetime.now()
    is_live_trading = current_date >= datetime(2026, 7, 1)
    status_label = "🛒 实盘正式开火" if is_live_trading else "🧪 2026实战模拟推演期"
    print(f"🚀 启动系统 [当前状态：{status_label}]...")

    try:
        vfc = yf.Ticker(VIX_ANCHOR)
        vix_hist = vfc.history(period="5d").dropna(subset=['Close'])
        current_vix = float(vix_hist['Close'].iloc[-1])
        
        sector = yf.Ticker(SECTOR_ANCHOR)
        # 宏观大盘指数也强行支持盘前盘后穿透计算，提前捕获隔夜黑天鹅
        sector_hist = sector.history(period="250d", prepost=True).dropna(subset=['Close'])
        
        high_low = sector_hist['High'] - sector_hist['Low']
        high_close = (sector_hist['High'] - sector_hist['Close'].shift()).abs()
        low_close = (sector_hist['Low'] - sector_hist['Close'].shift()).abs()
        tr = high_low.combine(high_close, max).combine(low_close, max)
        
        deltas = sector_hist['Close'].diff().dropna()
        gains = deltas.clip(lower=0)
        losses = -deltas.clip(upper=0)
        avg_gain = gains.ewm(com=13, min_periods=14).mean()
        avg_loss = losses.ewm(com=13, min_periods=14).mean()
        rs = avg_gain / avg_loss
        sector_rsi = 100 if float(avg_loss.iloc[-1]) == 0 else (100 - (100 / (1 + rs))).iloc[-1]
    except Exception as e:
        print(f"❌ 宏观大盘指数获取失败: {e}")
        return

    if current_vix >= 35:
        allocation_ratio = 0.60
        vix_strategy = "💥 历史级恐慌暴跌，非理性踩踏彻底释放！系统下发大仓位极限加码指令。"
    elif 25 <= current_vix < 35:
        allocation_ratio = 0.30
        vix_strategy = "🌊 市场处于标准中级周期黄金坑，建议动用 30% 储备子弹分批越跌越买。"
    else:
        allocation_ratio = 0.10
        vix_strategy = "⚖ 大盘微幅正常回调，后续仍有探底风险，建议轻仓试探建仓。"

    current_flexible_spend = LONG_TERM_FLEXIBLE_RESERVE * allocation_ratio
    any_triggered = False

    for etf_symbol in INTELLIGENT_ETFS:
        if process_stock_signal(etf_symbol, True, current_vix, sector_rsi, vix_strategy, current_flexible_spend, status_label):
            any_triggered = True

    for stock_symbol in LONG_TERM_STOCKS:
        if process_stock_signal(stock_symbol, False, current_vix, sector_rsi, vix_strategy, current_flexible_spend, status_label):
            any_triggered = True

    if not any_triggered:
        encoded_title = urllib.parse.quote_plus("🟢 长线加码雷达：安全站岗中")
        encoded_content = urllib.parse.quote_plus(f"核心量化指标检测完毕（包含盘前全量穿透）。当前大盘风控 VIX: {current_vix:.2f} | 行业芯片 RSI: {sector_rsi:.1f}。无雷股异动。")
        url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=系统状态&sound=none&isArchive=1"
        if BARK_KEY: requests.get(url, timeout=10)

if __name__ == "__main__":
    execute_combined_diagnosis()
