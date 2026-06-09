import os
import sys
import time
import urllib.parse
import requests
import yfinance as yf

BARK_KEY = os.environ.get("BARK_KEY")

# 🎯 升级后的全球冷门瓶颈庄股/隐形冠军池（从 6 只横向扩充至 14 只，覆盖三大硬科技赛道）
MONITOR_STOCKS = [
    "AXTI", "SIVNF", "XFABF", "WOLF", "VICR", "AAOI",  # 原 Serenity 核心股
    "POETF", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI" # 新增：全球硬科技瓶颈股
]

MARKET_CAP_MIN = 100_000_000      # 市值下限：1亿美元
MARKET_CAP_MAX = 6_000_000_000    # 市值上限：60亿美元（严格锚定高弹性小盘股）
VOLUME_MULTIPLIER = 3.0           # 3.0 倍日线成交量爆破阈值

def send_to_bark(title: str, content: str, group: str = "Serenity冷门爆款"):
    if not BARK_KEY:
        print(f"⚠️ 本地控制台输出 -> 【{title}】: {content}")
        return
    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200: print(f"🔔 成功推送 Bark 通知：{title}")
    except Exception as e: print(f"❌ 推送失败: {e}")

def execute_serenity_strategy():
    print(f"🚀 启动 [全球 {len(MONITOR_STOCKS)} 只隐形冠军小盘股放量扫描系统]...")
    for ticker_symbol in MONITOR_STOCKS:
        try:
            print(f"⏳ 正在交叉检索成交量: {ticker_symbol} ...")
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            market_cap = info.get("marketCap", 0)
            
            # 严格的小盘卡点市值过滤器
            if market_cap is None or market_cap == 0: continue
            if not (MARKET_CAP_MIN <= market_cap <= MARKET_CAP_MAX): 
                print(f"   ℹ️ 跳过 {ticker_symbol}: 当前市值 ${market_cap:,.0f} 超出 1亿-60亿 游击选股区间。")
                continue
                
            hist = ticker.history(period="35d")
            if len(hist) < 31: continue
                
            today_volume = hist['Volume'].iloc[-1]
            past_30_days_volume = hist['Volume'].iloc[-31:-1]
            avg_volume_30d = past_30_days_volume.mean()
            current_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            current_price = hist['Close'].iloc[-1]
            
            print(f"   📊 今日成交量倍数: {current_multiplier:.2f}x")
            
            if current_multiplier >= VOLUME_MULTIPLIER:
                # 依据单次 800 美元的严格游击纪律，自动计算应买入股数
                suggested_shares = 800 / current_price if current_price > 0 else 0
                
                send_to_bark(
                    f"🚨 核心爆破：【{ticker_symbol}】主力资金强烈扫货！", 
                    f"💰 实时价格: ${current_price:.2f} | 异常放量: {current_multiplier:.2f}倍\n"
                    f"------------------------\n"
                    f"🎯 【全球瓶颈股低配比突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】 (约合 6,240 港币)\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"📝 纪律: 资金来自 1w 美元敢死队。池内含 14 只精锐，防守极强，有信号再动，破位严执行止损！", 
                    "Serenity冷门爆款"
                )
            # 🌟 优化防封锁延时：由于标的增加，单次请求后小幅休眠 1.5 秒
            time.sleep(1.5)
        except Exception as e: 
            time.sleep(1)
            continue

if __name__ == "__main__":
    execute_serenity_strategy()
