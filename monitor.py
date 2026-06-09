import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf
from finvizfinance.screener.overview import Overview

BARK_KEY = os.environ.get("BARK_KEY")

MARKET_CAP_MIN = 100_000_000      
MARKET_CAP_MAX = 3_000_000_000    
VOLUME_MULTIPLIER = 3.0           
BLACK_SWAN_VOLUME_MULTIPLIER = 4.5  

SINGLE_SNIPER_BUDGET_USD = 800


def send_to_bark_with_override(title: str, content: str, multiplier: float, group: str = "全美股主力爆破"):
    """带有开盘半小时扩容时间锁的 Bark 推送端"""
    if not BARK_KEY:
        print(f"⚠️ 本地控制台输出 -> 【{title}】: {content}")
        return

    # 1. 检查北京时间
    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    bj_minute = bj_time.minute
    current_total_minutes = bj_hour * 60 + bj_minute
    
    start_allowed_minutes = 8 * 60         
    end_allowed_minutes = 22 * 60        # ✨ 精准修改：晚上 22:00
    is_sleep_hours = not (start_allowed_minutes <= current_total_minutes <= end_allowed_minutes)

    # 2. 个股重大天量熔断特权
    if is_sleep_hours and multiplier >= BLACK_SWAN_VOLUME_MULTIPLIER:
        print(f"🚨🚨 【个股特大异动特权触发】当前北京时间 {bj_time.strftime('%H:%M:%S')}，该股爆发了极其罕见的 {multiplier:.2f} 倍超大天量换手！系统强行击穿睡眠锁唤醒！")
        title = "🚨【特大突发黑天鹅/利好强推】" + title
    elif is_sleep_hours:
        print(f"💤 当前北京时间为 {bj_time.strftime('%H:%M:%S')}，个股处于常规主力扫货阶段倍数 ({multiplier:.2f}x)，静音拦截。")
        return

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200: print(f"🔔 成功推送 Bark 警报：{title}")
    except Exception as e: print(f"❌ 推送失败: {e}")


def fetch_us_stock_universe():
    print("🛰️ 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    try:
        fscreen = Overview()
        filters_dict = {
            'Market Cap.': 'Custom (100M to 3B)',
            'Country': 'USA',
            'Current Volume': 'Over 500K' 
        }
        fscreen.set_filter(filters_dict)
        df = fscreen.screener_view()
        if df is not None and not df.empty:
            return df['Ticker'].tolist()
        return []
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}")
        return ["AXTI", "SIVNF", "XFABF", "WOLF", "VICR", "AAOI", "POETF", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI"]


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
            
            if current_multiplier >= VOLUME_MULTIPLIER:
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / current_price if current_price > 0 else 0
                info = ticker.info
                real_market_cap = info.get("marketCap", 0)
                
                push_title = f"全美放量暴破：【{ticker_symbol}】主力强力扫货！"
                push_content = (
                    f"💰 实时收盘价: ${current_price:.2f} | 📊 异常放量: {current_multiplier:.2f}倍\n"
                    f"🏢 股票当前市值: ${real_market_cap/1_000_000:.1f}M\n"
                    f"------------------------\n"
                    f"🎯 【全美股大数据量化突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"📝 提示: 接收时段已放宽至晚上 22:00。包含了开盘前 30 分钟的疯狂换手扫描！"
                )
                send_to_bark_with_override(title=push_title, content=push_content, multiplier=current_multiplier, group="全美股主力爆破")
            time.sleep(1.2)
        except Exception as e: continue


if __name__ == "__main__":
    execute_all_us_strategy()
