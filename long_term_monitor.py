import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf

# ==================== 🏛 大师级实盘策略配置区域 ====================
BARK_KEY = os.environ.get("BARK_KEY")
VIX_ANCHOR = "^VIX"
SECTOR_ANCHOR = "SOXX"

# 核心修订：将大盘定投ETF与需要基本面筛选的个股进行【清晰分离】
INTELLIGENT_ETFS = ["VOO", "QQQ"]
LONG_TERM_STOCKS = ["GOOG"] 

ROE_THRESHOLD = 0.15
PE_MAX_THRESHOLD = 35
RSI_BUY_LINE = 35

# 💵 真实锁定：20,000 美元中长线机动储备金
LONG_TERM_FLEXIBLE_RESERVE = 20000
# ==================================================================

def send_to_bark_with_override(title: str, content: str, current_vix: float, group: str = "灵活资金加码雷达"):
    """⏰ 带有“黑天鹅熔断特权”的智能 Bark 推送端（时间已放宽至 08:00 ~ 22:00）"""
    if not BARK_KEY:
        print(f"\n ⚠ 控制台实时输出 -> \n【{title}】\n{content}\n")
        return

    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    bj_minute = bj_time.minute
    
    current_total_minutes = bj_hour * 60 + bj_minute
    start_allowed_minutes = 8 * 60
    end_allowed_minutes = 22 * 60
    is_sleep_hours = not (start_allowed_minutes <= current_total_minutes <= end_allowed_minutes)

    # 黑天鹅核心熔断逻辑：VIX >= 35 深夜强推唤醒
    if is_sleep_hours and current_vix >= 35:
        print(f"🚨🚨 【黑天鹅特权触发】VIX 达到 {current_vix:.2f}！系统深夜强行唤醒！")
        title = "🚨【黑天鹅大底强行唤醒】" + title
    elif is_sleep_hours:
        print(f"💤 当前北京时间为 {bj_time.strftime('%H:%M:%S')}，常规波动静音拦截。")
        return

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    
    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=calypso"
    try:
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: 
        return 50
    deltas = prices.diff().dropna()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.ewm(com=period-1, min_periods=period).mean()
    avg_loss = losses.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return (100 - (100 / (1 + rs))).iloc[-1]

def process_stock_signal(ticker_symbol: str, is_etf: bool, current_vix: float, sector_rsi: float, vix_strategy: str, current_flexible_spend: float, status_label: str):
    """独立处理每只标的的信号计算与推送，防止彼此干扰"""
    try:
        ticker = yf. Ticker(ticker_symbol)
        
        # 🛡 健壮性优化：针对个股进行严格的基本面初筛，防范 yfinance 返回 None
        if not is_etf:
            info = ticker.info
            if not info:
                print(f"⚠ 无法获取 {ticker_symbol} 的 info 数据，跳过基本面筛查。")
                return
                
            roe = info.get("returnOnEquity", 0)
            pe = info.get("trailingPE", 0)
            
            if roe is None or roe < ROE_THRESHOLD: 
                print(f"ℹ {ticker_symbol} ROE未达标或为None，当前: {roe}")
                return
            if pe is None or pe > PE_MAX_THRESHOLD or pe <= 0: 
                print(f"ℹ {ticker_symbol} PE超标或为None，当前: {pe}")
                return

        # 获取历史行情数据
        hist = ticker.history(period="250d")
        if len(hist) < 210: 
            return

        current_price = hist['Close'].iloc[-1]
        ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        current_rsi = calculate_rsi(hist['Close'])
        is_stock_above_ma200 = current_price > ma200

        # 🎯 触发核心逻辑：守住MA200牛熊生命线，且个股或行业极度超卖
        if is_stock_above_ma200 and (current_rsi <= RSI_BUY_LINE or sector_rsi <= 35):
            suggested_shares = current_flexible_spend / current_price if current_price > 0 else 0
            stop_loss_price = current_price * 0.93 # 7% 机械硬止损线

            push_title = f"💎 资产加码通知：【{ticker_symbol}】进入绝佳黄金坑！"
            push_content = (
                f"🏷 【当前系统阶段】: {status_label}\n"
                f"🧐 实时 VIX 恐慌指数: {current_vix:.2f} | 行业 RSI: {sector_rsi:.1f}\n"
                f"🗺 宏观风控大局观: {vix_strategy}\n"
                f"------------------------\n"
                f"💰 实时股价: ${current_price:.2f} (稳守牛熊生命线 ${ma200:.2f} 上方)\n"
                f"🚨 【储备金加码精准跟单】:\n"
                f"💵 本次分配子弹: 【 ${current_flexible_spend:,.0f} 美元 】\n"
                f"🛒 建议模拟买入股数: 【 {suggested_shares:.0f} 股 】\n"
                f"🛑 【华尔街防线】: 若买入，7% 机械硬止损价为 【 ${stop_loss_price:.2f} 】\n"
                f"------------------------\n"
                f"📅 【每月发薪日正规军强制纪律单】:\n"
                f"💵 工资分配: 发薪后 $1,400 新资金请分别对半 700 美元买入 VOO 与 QQQ 底仓！"
            )
            send_to_bark_with_override(title=push_title, content=push_content, current_vix=current_vix, group="灵活资金加码雷达")
            time.sleep(1)
    except Exception as e:
        print(f"❌ 处理 {ticker_symbol} 时发生未知错误: {e}")

def execute_combined_diagnosis():
    current_date = datetime.now()
    is_live_trading = current_date >= datetime(2026, 7, 1)
    status_label = "🛒 实盘正式开火" if is_live_trading else "🧪 2026实战模拟推演期 (7月1日正式记账)"
    print(f"🚀 启动系统 [当前状态：{status_label}]...")

    try:
        vfc = yf.Ticker(VIX_ANCHOR)
        current_vix = vfc.history(period="5d")['Close'].iloc[-1]
        
        sector = yf.Ticker(SECTOR_ANCHOR)
        sector_rsi = calculate_rsi(sector.history(period="250d")['Close'])
    except Exception as e:
        print(f"❌ 宏观大盘指数获取失败: {e}")
        return

    # 宏观控仓策略分配
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

    # 1. 先处理大盘定投型 ETF（不进行基本面 ROE/PE 过滤）
    for etf_symbol in INTELLIGENT_ETFS:
        process_stock_signal(
            ticker_symbol=etf_symbol, 
            is_etf=True, 
            current_vix=current_vix, 
            sector_rsi=sector_rsi, 
            vix_strategy=vix_strategy, 
            current_flexible_spend=current_flexible_spend, 
            status_label=status_label
        )

    # 2. 再处理精选长线个股（进行严格的基本面 ROE/PE 过滤）
    for stock_symbol in LONG_TERM_STOCKS:
        process_stock_signal(
            ticker_symbol=stock_symbol, 
            is_etf=False, 
            current_vix=current_vix, 
            sector_rsi=sector_rsi, 
            vix_strategy=vix_strategy, 
            current_flexible_spend=current_flexible_spend, 
            status_label=status_label
        )

if __name__ == "__main__":
    execute_combined_diagnosis()
