import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf
from finvizfinance.screener.overview import Overview

BARK_KEY = os.environ.get("BARK_KEY")

VOLUME_MULTIPLIER = 3.0           
BLACK_SWAN_VOLUME_MULTIPLIER = 4.5  
SINGLE_SNIPER_BUDGET_USD = 800


def send_to_bark_with_override(title: str, content: str, multiplier: float, group: str = "全美股主力爆破"):
    """✨ 核心改进：解除对 Bark 推送的网络截断，允许从今天起发送实时战术情报！"""
    if not BARK_KEY:
        print(f"⚠️ 本地控制台输出 -> 【{title}】: {content}")
        return

    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    bj_minute = bj_time.minute
    current_total_minutes = bj_hour * 60 + bj_minute
    
    start_allowed_minutes = 8 * 60         
    end_allowed_minutes = 22 * 60        
    is_sleep_hours = not (start_allowed_minutes <= current_total_minutes <= end_allowed_minutes)

    if is_sleep_hours and multiplier >= BLACK_SWAN_VOLUME_MULTIPLIER:
        print(f"🚨🚨 【特大突过载强推】")
        title = "🚨【特大突发黑天鹅/利好强推】" + title
    elif is_sleep_hours:
        print(f"💤 夜间常规放量 ({multiplier:.2f}x)，静音拦截。")
        return

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200: print(f"🔔 成功推送 Bark 警报：{title}")
    except Exception as e: print(f"❌ 推送失败: {e}")


def fetch_us_stock_universe():
    print("🛰️ 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    try:
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        df = fscreen.screener_view()
        if df is not None and not df.empty:
            return df['Ticker'].tolist()
        return []
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}，启动 14 只卡点标的...")
        return ["AXTI", "WOLF", "XFABF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX"]


def execute_all_us_strategy():
    dynamic_stocks = fetch_us_stock_universe()
    print(f"🚀 精准对齐启动 [全美股 {len(dynamic_stocks)} 只小盘股成交量穿透判别]...")
    
    for ticker_symbol in dynamic_stocks[:40]:
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="35d")
            if len(hist) < 31: continue
                
            today_volume = hist['Volume'].iloc[-1]
            past_30_days_volume = hist['Volume'].iloc[-31:-1]
            avg_volume_30d = past_30_days_volume.mean()
            current_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            current_price = hist['Close'].iloc[-1]
            
            print(f"   📊 标的 {ticker_symbol} -> 今日量倍数: {current_multiplier:.2f}x")
            
            if current_multiplier >= VOLUME_MULTIPLIER:
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / current_price if current_price > 0 else 0
                
                # ✨ 核心改进：自动计算冷门狙击股的 7% 硬割肉防线价格
                stop_loss_price = current_price * 0.93
                
                push_title = f"全美放量爆破：【{ticker_symbol}】主力强力扫货！"
                push_content = (
                    f"🏷️ 【当前系统阶段】: 🧪 2026实战模拟推演期 (7月1日正式记账)\n"
                    f"💰 实时收盘价: ${current_price:.2f} | 📊 异常放量: {current_multiplier:.2f}倍\n"
                    f"------------------------\n"
                    f"🎯 【全美股大数据量化突击单】:\n"
                    f"💵 本笔固定拨发游击子弹: 【 $800 美元 】\n"
                    f"🛒 建议模拟买入股数: 【 {suggested_shares:.0f} 股 】\n"
                    f"🛑 【华尔街防线】: 若买入，7% 机械硬止损价为 【 ${stop_loss_price:.2f} 】 (跌破严禁抗单！)\n"
                    f"------------------------\n"
                    f"📝 提示: 接收时段已限制在北京时间 08:00~22:00。"
                )
                send_to_bark_with_override(title=push_title, content=push_content, multiplier=current_multiplier, group="全美股主力爆破")
            time.sleep(1.2)
        except Exception as e: continue


if __name__ == "__main__":
    execute_all_us_strategy()
