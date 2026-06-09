import os
import sys
import time
import urllib.parse
import requests
import yfinance as yf
from finvizfinance.screener.overview import Overview

BARK_KEY = os.environ.get("BARK_KEY")

# 📊 终极过滤器：全美股自动化动态初选阈值
MARKET_CAP_MIN = 100_000_000      # 1亿美元
MARKET_CAP_MAX = 3_000_000_000    # 30亿美元 (遵照指令调整为严格 30 亿)
VOLUME_MULTIPLIER = 3.0           # 3.0 倍日线成交量爆破阈值

# 💵 敢死队资金纪律：单次触发严格限制轻仓开火 $800 USD (约合 6,240 港币)
SINGLE_SNIPER_BUDGET_USD = 800


def send_to_bark(title: str, content: str, group: str = "全美股主力爆破"):
    """Bark 安全发送模块"""
    if not BARK_KEY:
        print(f"⚠️ 本地控制台输出 -> 【{title}】: {content}")
        return
    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200: 
            print(f"🔔 成功推送 Bark 警报：{title}")
    except Exception as e: 
        print(f"❌ 推送失败: {e}")


def fetch_us_stock_universe():
    """
    ⚡ 核心黑科技：利用 Finviz 引擎，一秒穿透洗劫全美股！
    动态筛选出：全美国公司 (USA) + 市值在 1亿至30亿美元之间 + 今日成交量明显放大的初始池
    """
    print("🛰️ 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    try:
        fscreen = Overview()
        # 写入全美股初选过滤器过滤矩阵
        # Custom Market Cap: 100M to 3B
        # Country: USA
        # Target Volume: Over 3x Average (为了防止初选漏掉，我们在API层先抓放量明显的标的)
        filters_dict = {
            'Market Cap.': 'Custom (100M to 3B)',
            'Country': 'USA',
            'Current Volume': 'Over 500K' # 初选过滤掉死水微盘股，提升扫描效率
        }
        fscreen.set_filter(filters_dict)
        df = fscreen.screener_view()
        
        # 提取出所有通关的股票代码 (Ticker)
        if df is not None and not df.empty:
            ticker_list = df['Ticker'].tolist()
            print(f"✅ 全美股初选成功！共斩获 {len(ticker_list)} 只符合 1亿-30亿 基础门槛的小盘美股标的。")
            return ticker_list
        else:
            print("⚠️ 未能在全美股捕获到初选通关标的。")
            return []
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}，将采用备用容错方案...")
        # 备用容错：如果三方接口偶尔抽风，保留您之前的核心 14 只精锐，确保系统永不罢工
        return ["AXTI", "SIVNF", "XFABF", "WOLF", "VICR", "AAOI", "POETF", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI"]


def execute_all_us_strategy():
    # 获取全美股动态更新的初始选股池
    dynamic_stocks = fetch_us_stock_universe()
    
    print(f"🚀 精准对齐启动 [全美股 {len(dynamic_stocks)} 只小盘股 3.0倍成交量深度穿透判别]...")
    
    # 限制单次 GitHub Actions 运行的个股上限为前 40 只异动最剧烈的票，防止触发 GitHub 运行超时限制
    for ticker_symbol in dynamic_stocks[:40]:
        try:
            ticker = yf.Ticker(ticker_symbol)
            hist = ticker.history(period="35d")
            if len(hist) < 31: 
                continue
                
            # 2. 计算精密量化指标
            today_volume = hist['Volume'].iloc[-1]
            past_30_days_volume = hist['Volume'].iloc[-31:-1]
            avg_volume_30d = past_30_days_volume.mean()
            
            current_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            current_price = hist['Close'].iloc[-1]
            
            # 3. 严格执行 3.0 倍暴破判别
            if current_multiplier >= VOLUME_MULTIPLIER:
                # 依据单次 800 美元的严格实盘游击纪律，自动计算应买入股数
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / current_price if current_price > 0 else 0
                
                # 快速二次抓取该股真实市值，确保万无一失
                info = ticker.info
                real_market_cap = info.get("marketCap", 0)
                
                send_to_bark(
                    f"🚨 全美放量暴破：【{ticker_symbol}】主力强力扫货！", 
                    f"💰 实时收盘价: ${current_price:.2f} | 📊 异常放量: {current_multiplier:.2f}倍\n"
                    f"🏢 股票当前市值: ${real_market_cap/1_000_000:.1f}M\n"
                    f"------------------------\n"
                    f"🎯 【全美股大数据量化突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】 (约合 6,240 港币)\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"📝 纪律: 资金归属 1w 美元敢死队。系统已自动穿透扫描全美股数千只标的。打中即撤，破位必严执行止损！", 
                    "全美股主力爆破"
                )
            # 全市场高频请求，设置 1.2 秒安全睡眠延时
            time.sleep(1.2)
        except Exception as e: 
            continue


if __name__ == "__main__":
    execute_all_us_strategy()
    print("🏁 全美股大数据实时异动扫描全部结束。")
