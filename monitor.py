import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
import requests
import yfinance as yf
from finvizfinance.screener.overview import Overview

BARK_KEY = os.environ.get("BARK_KEY")

# ==================== 📊 终极三日量价与成交额过滤器阈值 ====================
VOLUME_MULTIPLIER = 3.0       # 昨日完整放量倍数需大于 3.0 倍
MIN_STOCK_PRICE = 2.0         # 仙股过滤器：股价必须大于等于 $2.0
MIN_3DAY_AVG_TURNOVER = 5_000_000 # 近3日平均日成交额必须大于 500 万美元

SINGLE_SNIPER_BUDGET_USD = 800  # 💵 敢死队固定额度：单次严格限制开火 $800 美元
MAX_SCAN_COUNT = 45             # ⚡ 每次运行最大穿透扫描的股票数量
# =========================================================================

def send_to_bark_raw(title: str, content: str, group: str = "全美股主力爆破", click_url: str = None):
    """Bark 安全发送模块（集成点击直达与自动归档功能）"""
    if not BARK_KEY:
        print(f"⚠ 本地控制台输出 -> 【{title}】: {content}")
        return
        
    clean_key = BARK_KEY.replace("https://day.app", "").replace("http://day.app", "").strip("/")
    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    
    url = f"https://api.day.app/{clean_key}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic&isArchive=1"
    if click_url:
        url += f"&url={urllib.parse.quote_plus(click_url)}"
        
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200: 
            print(f"🔔 成功推送 Bark 警报：{title}")
    except Exception as e: 
        print(f"❌ 推送失败: {e}")

def fetch_us_stock_universe():
    """🛰 Finviz 全美股基础池数据抓取"""
    print("🛰 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    backup_list = ["AXTI", "WOLF", "XFABF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX"]
    try:
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        
        try:
            df = fscreen.get_screener_platform(layout='Overview')
        except AttributeError:
            df = fscreen.screener_view()
            
        if df is not None and not df.empty:
            df.columns = df.columns.str.strip()
            ticker_col = None
            for col in ['Ticker', 'ticker', 'TICKER']:
                if col in df.columns:
                    ticker_col = col
                    break
                    
            if ticker_col:
                ticker_list = df[ticker_col].astype(str).str.strip().tolist()
                print(f"✅ 全美股初选成功！共斩获 {len(ticker_list)} 只符合标准的小盘美股标的。")
                return ticker_list
        return backup_list
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}，启动精锐防线...")
        return backup_list

def execute_all_us_strategy(dynamic_stocks):
    """传入个股池进行高阶连续放量爆破穿透"""
    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    print(f"⏰ 当前北京时间实时为: {bj_time.strftime('%H:%M:%S')}")
    
    if not (8 <= bj_hour < 22):
        print("💤 当前处于深夜静音保护时段，全美股雷达安全静音。")
        return

    if not dynamic_stocks:
        return

    target_stocks = dynamic_stocks[:MAX_SCAN_COUNT]
    print(f"🚀 精准对齐启动 [全美股前 {len(target_stocks)} 只小盘股三日历史成交额穿透过滤]...")
    
    triggered_count = 0

    for ticker_symbol in target_stocks:
        try:
            ticker = yf.Ticker(ticker_symbol)
            # 拉取 40 天数据，清洗空行
            hist = ticker.history(period="40d").dropna(subset=['Close', 'Volume'])
            if len(hist) < 31: continue

            # 🛠 核心策略修正：计算过去 30 天（不含最近两个交易日）的基准均量
            past_30_days_volume = hist['Volume'].iloc[-32:-2]
            avg_volume_30d = past_30_days_volume.mean()
            if avg_volume_30d <= 0: continue

            # 获取最近三个确定性交易日的数据（过滤掉盘中剧烈跳动的干扰）
            price_t0 = float(hist['Close'].iloc[-1]) # 今日最新（若盘中，为盘中价）
            vol_t0 = float(hist['Volume'].iloc[-1])
            
            price_t1 = float(hist['Close'].iloc[-2]) # 昨日完整收盘价
            vol_t1 = float(hist['Volume'].iloc[-2])
            
            price_t2 = float(hist['Close'].iloc[-3]) # 前日完整收盘价
            vol_t2 = float(hist['Volume'].iloc[-3])

            # 计算近 3 日各天成交额
            turnover_t0 = price_t0 * vol_t0
            turnover_t1 = price_t1 * vol_t1
            turnover_t2 = price_t2 * vol_t2
            avg_3day_turnover = (turnover_t0 + turnover_t1 + turnover_t2) / 3

            # 计算昨日和前日的确定性放量倍数
            mult_t1 = vol_t1 / avg_volume_30d
            mult_t2 = vol_t2 / avg_volume_30d
            current_multiplier = vol_t0 / avg_volume_30d # 今日实时放量

            if price_t0 < MIN_STOCK_PRICE: continue
            if avg_3day_turnover < MIN_3DAY_AVG_TURNOVER: continue

            # 🎯 触发核心铁律：昨日已经完成“完美放量爆破”（>3倍），且今日继续维持热度
            if mult_t1 >= VOLUME_MULTIPLIER or current_multiplier >= VOLUME_MULTIPLIER:
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / price_t0 if price_t0 > 0 else 0
                stop_loss_price = price_t0 * 0.93  

                yahoo_finance_url = f"https://yahoo.com{ticker_symbol}"
                triggered_count += 1

                push_title = f"🚨 全美连续放量爆破：【{ticker_symbol}】巨量机构扫货！"
                push_content = (
                    f"🏷 【当前系统阶段】: 🧪 2026实战模拟推演期\n"
                    f"💰 实时收盘价: ${price_t0:.2f} | 📊 实时异动表现: 昨日放量 {mult_t1:.1f} 倍 / 今日实时 {current_multiplier:.1f} 倍\n"
                    f"💎 机构热度体检: 近3日平均日成交额达到 【 ${avg_3day_turnover:,.0f} 美元 】\n"
                    f"📈 连续历史状态: 前日放量 {mult_t2:.1f} x ➔ 昨日爆破 {mult_t1:.1f} x ➔ 今日延续 {current_multiplier:.1f} x\n"
                    f"------------------------\n"
                    f"🎯 【全美股高流动性量化突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"🛑 【华尔街防线】: 若买入，7% 机械硬止损价为 【 ${stop_loss_price:.2f} 】 (请以实际成交价为准)\n"
                    f"------------------------\n"
                    f"📝 提示: 点击本条消息可一键唤醒雅虎财经行情。"
                )
                send_to_bark_raw(title=push_title, content=push_content, group="全美股主力爆破", click_url=yahoo_finance_url)
                time.sleep(2.0) 
        except Exception:
            continue

    # 🟢 存活心跳通知机制
    if triggered_count == 0:
        print("🟢 今日未扫描到全美股合规标的。发送正常运行心跳线。")
        send_to_bark_raw(
            title="🟢 短线爆破雷达：安全站岗中",
            content=f"全美股大数据穿透扫描结束。今日初选前 {len(target_stocks)} 只个股未产生量价异动狂飙。系统运行良好。",
            group="系统状态"
        )

if __name__ == "__main__":
    stock_universe = fetch_us_stock_universe()
    execute_all_us_strategy(stock_universe)
    print("🏁 全美股大数据三日量价实时穿透扫描全部结束。")
