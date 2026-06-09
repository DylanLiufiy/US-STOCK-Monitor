import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf

# ==================== 🏛️ 大师级实盘策略配置区域 ====================
BARK_KEY = os.environ.get("BARK_KEY")

VIX_ANCHOR = "^VIX"
SECTOR_ANCHOR = "SOXX"
LONG_TERM_STOCKS = ["VOO", "QQQ", "GOOG"]

ROE_THRESHOLD = 0.15              
PE_MAX_THRESHOLD = 35             
RSI_BUY_LINE = 35                 

LONG_TERM_FLEXIBLE_RESERVE = 20000
# ==================================================================


def send_to_bark_with_override(title: str, content: str, current_vix: float, group: str = "灵活资金加码雷达"):
    """
    ⏰ 带有“黑天鹅熔断特权”的智能 Bark 推送端（时间已调整为 08:00 ~ 22:00）
    """
    if not BARK_KEY:
        print(f"\n⚠️ 网页端/控制台实时诊断输出 -> \n【{title}】\n{content}\n")
        return

    # 1. 检查当前北京时间
    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    bj_minute = bj_time.minute
    current_total_minutes = bj_hour * 60 + bj_minute
    
    start_allowed_minutes = 8 * 60         # 早上 08:00
    end_allowed_minutes = 22 * 60         # ✨ 精准修改：晚上 22:00

    is_sleep_hours = not (start_allowed_minutes <= current_total_minutes <= end_allowed_minutes)

    # 2. 黑天鹅核心熔断逻辑
    if is_sleep_hours and current_vix >= 35:
        print(f"🚨🚨 【黑天鹅特权触发】当前北京时间 {bj_time.strftime('%H:%M:%S')}，虽处于深夜，但 VIX 指数达到 {current_vix:.2f} 爆表状态！系统强行击穿睡眠锁发送高危推送！")
        title = "🚨【黑天鹅大底强行唤醒】" + title
    elif is_sleep_hours:
        print(f"💤 当前北京时间为 {bj_time.strftime('%H:%M:%S')}，市场处于常规波动 (VIX: {current_vix:.2f})，静音拦截，不打扰主人。")
        return

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=calypso"
    try: requests.get(url, timeout=10)
    except Exception as e: print(f"❌ 推送失败: {e}")


def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = prices.diff().dropna()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.ewm(com=period-1, min_periods=period).mean()
    avg_loss = losses.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return (100 - (100 / (1 + rs))).iloc[-1]


def execute_combined_diagnosis():
    current_date = datetime.now()
    is_live_trading = current_date >= datetime(2026, 7, 1)
    status_label = "🛒 实盘正式开火" if is_live_trading else "⚠️ 模拟备战观望期 (7月1日正式记账)"
    
    print(f"🚀 启动系统 [当前状态：{status_label}]...")
    
    try:
        vfc = yf.Ticker(VIX_ANCHOR)
        current_vix = vfc.history(period="5d")['Close'].iloc[-1]
        sector = yf.Ticker(SECTOR_ANCHOR)
        sector_rsi = calculate_rsi(sector.history(period="250d")['Close'])
    except Exception as e: return

    if current_vix >= 35:
        allocation_ratio = 0.60  
        vix_strategy = "💥 历史级恐慌暴跌，非理性踩踏彻底释放！系统下发大仓位极限加码指令。"
    elif 25 <= current_vix < 35:
        allocation_ratio = 0.30  
        vix_strategy = "🌊 市场处于标准中级周期黄金坑，建议动用 30% 储备子弹分批越跌越买。"
    else:
        allocation_ratio = 0.10  
        vix_strategy = "⚖️ 大盘微幅正常回调，后续仍有探底风险，建议轻仓试探建仓。"

    current_flexible_spend = LONG_TERM_FLEXIBLE_RESERVE * allocation_ratio

    for ticker_symbol in LONG_TERM_STOCKS:
        try:
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            if ticker_symbol not in ["VOO", "QQQ"]:
                roe = info.get("returnOnEquity", 0)
                pe = info.get("trailingPE", 0)
                if roe is None or roe < ROE_THRESHOLD: continue
                if pe is None or pe > PE_MAX_THRESHOLD or pe == 0: continue

            hist = ticker.history(period="250d")
            if len(hist) < 210: continue
            current_price = hist['Close'].iloc[-1]
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            current_rsi = calculate_rsi(hist['Close'])
            is_stock_above_ma200 = current_price > ma200
            
            if is_stock_above_ma200 and (current_rsi <= RSI_BUY_LINE or sector_rsi <= 35):
                suggested_shares = current_flexible_spend / current_price if current_price > 0 else 0
                push_title = f"💎 资产加码通知：【{ticker_symbol}】进入绝佳黄金坑！"
                push_content = (
                    f"🏷️ 【系统运行状态】: {status_label}\n"
                    f"🧐 实时 VIX 恐慌指数: {current_vix:.2f} | 行业 RSI: {sector_rsi:.1f}\n"
                    f"🗺️ 宏观风控大局观: {vix_strategy}\n"
                    f"------------------------\n"
                    f"💰 实时股价: ${current_price:.2f} (稳守牛熊生命线 ${ma200:.2f} 上方)\n"
                    f"🚨 【2万美元储备金大票加码执行单】:\n"
                    f"💵 本次建议划扣储备弹药: 【 ${current_flexible_spend:,.0f} 美元 】\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"------------------------\n"
                    f"📅 【每月发薪日正规军强制纪律单】:\n"
                    f"💵 工资额度分配: 请确保本月到账收入中，已分别划扣 700 美元 定额定投无条件买入 VOO 与 QQQ 底仓！\n"
                    f"📝 注: 接收时段已限制在北京时间 08:00~22:00 之间。夜间全自动静音拦截。"
                )
                send_to_bark_with_override(title=push_title, content=push_content, current_vix=current_vix, group="灵活资金加码雷达")
            time.sleep(1)
        except Exception as e: continue

if __name__ == "__main__":
    execute_combined_diagnosis()
