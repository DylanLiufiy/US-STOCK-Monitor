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
VOLUME_MULTIPLIER = 3.0       # 今日成交量突破线：需大于 30天均量的 3.0 倍
MIN_STOCK_PRICE = 2.0         # 仙股过滤器：股价必须大于等于 $2.0
MIN_3DAY_AVG_TURNOVER = 5_000_000 # 近3日平均日成交额必须大于 500 万美元

SINGLE_SNIPER_BUDGET_USD = 800  # 💵 敢死队固定额度：单次严格限制开火 $800 美元
MAX_SCAN_COUNT = 45             # ⚡ 每次运行最大穿透扫描的股票数量，防止 yfinance 触发反爬封锁
# =========================================================================

def send_to_bark_raw(title: str, content: str, group: str = "全美股主力爆破"):
    """Bark 安全发送模块"""
    if not BARK_KEY:
        print(f"⚠ 本地控制台输出 -> 【{title}】: {content}")
        return
        
    clean_key = BARK_KEY.replace("https://day.app", "").replace("http://day.app", "").strip("/")
    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    
    url = f"https://api.day.app/{clean_key}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200: 
            print(f"B🔔 成功推送 Bark 警报：{title}")
    except Exception as e: 
        print(f"❌ 推送失败: {e}")

def fetch_us_stock_universe():
    """🛰 Finviz 全美股基础池数据抓取"""
    print("🛰 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    backup_list = ["AXTI", "WOLF", "XFABF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX"]
    try:
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        
        # 兼容最新版 finvizfinance 接口标准
        try:
            df = fscreen.get_screener_platform(layout='Overview')
        except AttributeError:
            df = fscreen.screener_view()
            
        if df is not None and not df.empty:
            # 🛡 强健性清洗：防范接口返回的列名包含隐藏空格或大小写错位
            df.columns = df.columns.str.strip()
            
            ticker_col = None
            for col in ['Ticker', 'ticker', 'TICKER']:
                if col in df.columns:
                    ticker_col = col
                    break
                    
            if ticker_col:
                ticker_list = df[ticker_col].astype(str).str.strip().tolist()
                print(f"✅ 全美股初选成功！共斩获 {len(ticker_list)} 只符合华尔街标准小盘门槛的美股标的。")
                return ticker_list
                
        print("⚠ 无法解析 DataFrame 结构中的 Ticker 列，启动硬科技后备防线...")
        return backup_list
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}，系统已无缝启动 14 只核心硬科技精锐防线...")
        return backup_list

def execute_all_us_strategy(dynamic_stocks):
    """传入基础个股池进行多维连续历史数据清洗与策略匹配"""
    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    print(f"⏰ 当前北京时间实时为: {bj_time.strftime('%H:%M:%S')}")
    
    # ⏱ 北京时间 08:00 ~ 22:00 允许推送，深夜自动拦截
    if not (8 <= bj_hour < 22):
        print("💤 当前处于深夜静音保护时段，全美股雷达在云端默默做日志。")
        return

    if not dynamic_stocks:
        print("❌ 传入的股票列表为空，停止策略诊断。")
        return

    # 使用全局统一配置的扫描切片限制，避免产生高频封锁
    target_stocks = dynamic_stocks[:MAX_SCAN_COUNT]
    print(f"🚀 精准对齐启动 [全美股前 {len(target_stocks)} 只小盘股三日历史成交额穿透过滤]...")

    for ticker_symbol in target_stocks:
        try:
            ticker = yf.Ticker(ticker_symbol)
            # 拉取 40 天 K 线以确保经过 dropna 过滤后依然留存至少 31 天有效数据
            hist = ticker.history(period="40d")
            
            # 🛡 核心数据防御：清洗盘中未收盘带来的 NaN 行数据，避免指标逻辑污染
            hist = hist.dropna(subset=['Close', 'Volume'])
            
            if len(hist) < 31: 
                continue

            # 计算 30 日历史平均成交量（不含今天）
            past_30_days_volume = hist['Volume'].iloc[-31:-1]
            avg_volume_30d = past_30_days_volume.mean()
            if avg_volume_30d <= 0: 
                continue

            # 强类型转换为 float，杜绝极端状态下的 numpy 对象计算溢出
            today_price = float(hist['Close'].iloc[-1])
            today_volume = float(hist['Volume'].iloc[-1])
            
            day_minus_1_price = float(hist['Close'].iloc[-2])
            day_minus_1_volume = float(hist['Volume'].iloc[-2])
            
            day_minus_2_price = float(hist['Close'].iloc[-3])
            day_minus_2_volume = float(hist['Volume'].iloc[-3])

            # ✨ 计算连续 3 天各自的真实成交额（Turnover = 股价 * 成交量）
            turnover_today = today_price * today_volume
            turnover_d1 = day_minus_1_price * day_minus_1_volume
            turnover_d2 = day_minus_2_price * day_minus_2_volume

            # 算出最近 3 个交易日的平均日成交额
            avg_3day_turnover = (turnover_today + turnover_d1 + turnover_d2) / 3

            # 计算放量倍数
            current_multiplier = today_volume / avg_volume_30d
            mult_d1 = day_minus_1_volume / avg_volume_30d
            mult_d2 = day_minus_2_volume / avg_volume_30d

            print(f" 📊 {ticker_symbol} -> 3日均日成交额: ${avg_3day_turnover:,.0f} | 今日放量: {current_multiplier:.2f} x")

            # ==================== 🪓 终极连续三日多维过滤器矩阵 ====================
            # 1. 过滤股价低于 2 美元的垃圾仙股
            if today_price < MIN_STOCK_PRICE: 
                continue

            # 2. 硬性卡死：近3日平均日成交额必须大于阈值，彻底剔除僵尸股
            if avg_3day_turnover < MIN_3DAY_AVG_TURNOVER: 
                continue

            # 3. 稳健爆破大铁律：今日量满足 3.0 倍突发爆破
            if current_multiplier >= VOLUME_MULTIPLIER:
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / today_price if today_price > 0 else 0
                stop_loss_price = today_price * 0.93  # 自动换算 7% 硬割肉价格

                push_title = f"🚨 全美连续放量爆破：【{ticker_symbol}】巨量机构扫货！"
                push_content = (
                    f"🏷 【当前系统阶段】: 🧪 2026实战模拟推演期\n"
                    f"💰 实时收盘价: ${today_price:.2f} | 📊 今日异常放量: {current_multiplier:.2f} 倍\n"
                    f"💎 机构热度体检: 近3日平均日成交额达到惊人的 【 ${avg_3day_turnover:,.0f} 美元 】\n"
                    f"📈 连续历史状态: 前日放量 {mult_d2:.1f} x ➔ 昨日放量 {mult_d1:.1f} x ➔ 今日爆破 {current_multiplier:.1f} x\n"
                    f"------------------------\n"
                    f"🎯 【全美股高流动性量化突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】\n"
                    f"🛒 建议即刻下单买入: 【 {suggested_shares:.0f} 股 】\n"
                    f"🛑 【华尔街防线】: 若买入，7% 机械硬止损价为 【 ${stop_loss_price:.2f} 】 (请以实际成交价为准)\n"
                    f"------------------------\n"
                    f"📝 提示: 系统已成功穿透过滤最近 3 天的量价与成交额。高质跟庄！"
                )
                send_to_bark_raw(title=push_title, content=push_content, group="全美股主力爆破")
                time.sleep(1.5) # 提高爬虫延时安全边际
        except Exception as e:
            print(f"⚠ 处理 {ticker_symbol} 时遇到未预期异常: {e}")
            continue

if __name__ == "__main__":
    # 修复原版逻辑中 fetch 两次、执行逻辑产生错位的硬伤
    stock_universe = fetch_us_stock_universe()
    execute_all_us_strategy(stock_universe)
    print("🏁 全美股大数据三日量价实时穿透扫描全部结束。")
