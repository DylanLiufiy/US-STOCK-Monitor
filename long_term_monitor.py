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

INTELLIGENT_ETFS = ["VOO", "QQQ"]
LONG_TERM_STOCKS = ["GOOG"] 

ROE_THRESHOLD = 0.15
PE_MAX_THRESHOLD = 35
RSI_BUY_LINE = 35

# 💵 真实锁定：20,000 美元中长线机动储备金
LONG_TERM_FLEXIBLE_RESERVE = 20000
# ==================================================================

def send_to_bark_with_override(title: str, content: str, current_vix: float, group: str = "灵活资金加码雷达", click_url: str = None):
    """⏰ 带有“黑天鹅熔断特权”与“点击直达”的智能 Bark 推送端"""
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

    if is_sleep_hours and current_vix >= 35:
        print(f"🚨🚨 【黑天鹅特权触发】VIX 达到 {current_vix:.2f}！系统深夜强行唤醒！")
        title = "🚨【黑天鹅大底强行唤醒】" + title
    elif is_sleep_hours:
        print(f"💤 当前北京时间为 {bj_time.strftime('%H:%M:%S')}，常规波动静音拦截。")
        return

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    
    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=calypso&isArchive=1"
    if click_url:
        url += f"&url={urllib.parse.quote_plus(click_url)}"
        
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
    
    if float(avg_loss.iloc[-1]) == 0:
        return 100
    return (100 - (100 / (1 + rs))).iloc[-1]

def process_stock_signal(ticker_symbol: str, is_etf: bool, current_vix: float, sector_rsi: float, vix_strategy: str, current_flexible_spend: float, status_label: str):
    """独立处理每只标的的信号计算与推送"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        if not is_etf:
            try:
                info = ticker.info
                roe = info.get("returnOnEquity", 0)
                pe = info.get("trailingPE", 0)
                
                if roe is None or roe < ROE_THRESHOLD: return False
                if pe is None or pe > PE_MAX_THRESHOLD or pe <= 0: return False
            except Exception:
                return False

        hist = ticker.history(period="250d").dropna(subset=['Close']) 
        if len(hist) < 210: return False

        current_price = float(hist['Close'].iloc[-1])
        ma200 = float(hist['Close'].rolling(window=200).mean().iloc[-1])
        current_rsi = calculate_rsi(hist['Close'])
        is_stock_above_ma200 = current_price > ma200

        if is_stock_above_ma200 and (current_rsi <= RSI_BUY_LINE or sector_rsi <= 35):
            suggested_shares = current_flexible_spend / current_price if current_price > 0 else 0
            stop_loss_price = current_price * 0.93 

            yahoo_finance_url = f"https://yahoo.com{ticker_symbol}"

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
                f"🛑 【华尔街防线】: 7% 机械硬止损价为 【 ${stop_loss_price:.2f} 】 (注: 请以实际成交价为准计算)\n"
                f"------------------------\n"
                f"📅 【每月发薪日正规军强制纪律单】:\n"
                f"💵 工资分配: 发薪后 $1,400 新资金请分别对半 700 美元买入 VOO 与 QQQ 底仓！\n\n"
                f"👉 提示: 手机端可点击此通知直接唤醒雅虎财经看盘。"
            )
            send_to_bark_with_override(
                title=push_title, 
                content=push_content, 
                current_vix=current_vix, 
                group="灵活资金加码雷达", 
                click_url=yahoo_finance_url
            )
            time.sleep(1.5)
            return True 
    except Exception as e:
        print(f"❌ 处理 {ticker_symbol} 异常: {e}")
    return False

def execute_combined_diagnosis():
    current_date = datetime.now()
    is_live_trading = current_date >= datetime(2026, 7, 1)
    status_label = "🛒 实盘正式开火" if is_live_trading else "🧪 2026实战模拟推演期 (7月1日正式记账)"
    print(f"🚀 启动系统 [当前状态：{status_label}]...")

    try:
        vfc = yf.Ticker(VIX_ANCHOR)
        vix_hist = vfc.history(period="5d").dropna(subset=['Close'])
        current_vix = float(vix_hist['Close'].iloc[-1])
        
        sector = yf.Ticker(SECTOR_ANCHOR)
        sector_hist = sector.history(period="250d").dropna(subset=['Close'])
        sector_rsi = calculate_rsi(sector_hist['Close'])
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

    # 🟢 存活心跳通知机制
    if not any_triggered:
        print("🟢 今日大盘行情平稳，长线策略未达黄金坑临界点。发送安全心跳线。")
        send_to_bark_with_override(
            title="🟢 长线加码雷达：安全站岗中",
            content=f"系统体检通过。当前大盘风控 VIX: {current_vix:.2f} | 行业芯片 RSI: {sector_rsi:.1f}。无加仓指令，请严格管住双手。",
            current_vix=current_vix,
            group="系统状态"
        )

if __name__ == "__main__":
    execute_combined_diagnosis()
