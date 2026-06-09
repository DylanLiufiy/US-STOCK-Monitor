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
SINGLE_SNIPER_BUDGET_USD = 800


def send_to_bark_with_override(title: str, content: str, multiplier: float, group: str = "全美股主力爆破"):
    if not BARK_KEY:
        print(f"⚠️ 本地控制台输出 -> 【{title}】: {content}")
        return
    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200: 
            print(f"🔔 成功推送 Bark 警报：{title}")
    except Exception as e: 
        print(f"❌ 推送失败: {e}")


def fetch_us_stock_universe():
    """
    🛰️ 终极通关：完美对齐官方内置内置标准 'Small ($300mln to $2bln)' 的全美股动态清洗引擎
    """
    print("🛰️ 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    try:
        fscreen = Overview()
        # ✨ ✨ 核心终极修复：将无法识别的 Custom 替换为官方完全兼容的标准小盘股区间 'Small ($300mln to $2bln)'
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        df = fscreen.screener_view()
        if df is not None and not df.empty:
            ticker_list = df['Ticker'].tolist()
            print(f"✅ 全美股初选成功！共斩获 {len(ticker_list)} 只符合华尔街标准小盘门槛的美股标的。")
            return ticker_list
        return []
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}，系统已无缝启动 14 只核心硬科技精锐防线...")
        return ["AXTI", "WOLF", "XFABF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX"]


def execute_all_us_strategy():
    dynamic_stocks = fetch_us_stock_universe()
    print(f"🚀 精准对齐启动 [全美股 {len(dynamic_stocks)} 只小盘股成交量穿透判别]...")
    
    # 限制单次扫描前 40 只异动个股，确保工作流不会因大数据发生 GitHub 超时
    for ticker_symbol in dynamic_stocks[:40]:
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="35d")
            if len(hist) < 31: 
                continue
                
            today_volume = hist['Volume'].iloc[-1]
            past_30_days_volume = hist['Volume'].iloc[-31:-1]
            avg_volume_30d = past_30_days_volume.mean()
            current_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            current_price = hist['Close'].iloc[-1]
            
            print(f"   📊 标的 {ticker_symbol} -> 今日量倍数: {current_multiplier:.2f}x")
            
            if current_multiplier >= VOLUME_MULTIPLIER:
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / current_price if current_price > 0 else 0
                
                push_title = f"全美放量爆破：【{ticker_symbol}】主力强力扫货！"
                push_content = (
                    f"💰 实时收盘价: ${current_price:.2f} | 📊 异常放量: {current_multiplier:.2f}倍\n"
                    f"------------------------\n"
                    f"🎯 【全美股大数据量化突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】 (约合 6,240 港币)\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"📝 提示: 接收时段已完美对齐北京时间 08:00~22:00。包含了开盘前半小时的大数据抓取！"
                )
                
                # 严格的时间防线校验
                bj_time = datetime.utcnow() + timedelta(hours=8)
                bj_hour = bj_time.hour
                if 8 <= bj_hour < 22:
                    encoded_title = urllib.parse.quote_plus(push_title)
                    encoded_content = urllib.parse.quote_plus(push_content)
                    url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=全美股主力爆破&sound=electronic"
                    requests.get(url, timeout=10)
            time.sleep(1.2)
        except Exception as e: 
            continue


if __name__ == "__main__":
    execute_all_us_strategy()
    print("🏁 全美股大数据实时异动扫描全部结束。")
