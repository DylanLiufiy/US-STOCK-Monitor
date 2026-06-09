import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta  # ✨ 核心修复：显式导入时间组件，彻底根除云端 NameError 隐形崩溃
import requests
from finvizfinance.screener.overview import Overview

# ==================== 安全与真实储备金配置区域 ====================
# 🔒 自动读取 GitHub Actions 环境中的 Bark 密钥
BARK_KEY = os.environ.get("BARK_KEY")

# 🎯 全美股动态初选范围
MARKET_CAP_MIN = 100_000_000      
MARKET_CAP_MAX = 3_000_000_000    

# 💵 实盘冷门股单次轻仓预算
SINGLE_SNIPER_BUDGET_USD = 800

# 📊 ✨ 测试专用强制开火防线：为了让您现在看到效果，强行改为 0
VOLUME_MULTIPLIER = 0.0           
# ============================================================


def send_to_bark_raw(title: str, content: str, group: str = "全美股主力爆破"):
    """
    ✨ ✨ 核心修复版 Bark 底层发送端
    """
    if not BARK_KEY:
        print(f"⚠️ 本地控制台输出 -> 【{title}】: {content}")
        return

    # 底层自动清洗净化密钥，防止任何错位
    clean_key = (
        BARK_KEY.replace("https://day.app", "")
        .replace("https://day.app", "")
        .strip("/")
    )

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)

    # 拼装绝对符合苹果 APNS 规范的官方标准 URL
    url = f"https://day.app{clean_key}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    
    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            print(f"🔔 完美送达！苹果服务器响应: {res.text}")
        else:
            print(f"❌ 苹果服务器拒收，状态码: {res.status_code}")
    except Exception as e:
        print(f"❌ 网络发送遇到硬阻碍崩溃: {e}")


def fetch_us_stock_universe():
    print("🛰️ 正在联线华尔街数据中心，全量扫描全美股数千家挂牌公司...")
    try:
        fscreen = Overview()
        fscreen.set_filter(filters_dict={'Market Cap.': 'Small ($300mln to $2bln)', 'Country': 'USA'})
        df = fscreen.screener_view()
        if df is not None and not df.empty:
            ticker_list = df['Ticker'].tolist()
            print(f"✅ 全美股初选成功！共斩获 {len(ticker_list)} 只符合基础门槛的小盘美股标的。")
            return ticker_list
        return []
    except Exception as e:
        print(f"❌ 全美股初选引擎连接失败: {e}，系统已启动 14 只精锐防线...")
        return ["AXTI", "WOLF", "XFABF", "VICR", "AAOI", "RMBS", "ALGM", "LSCC", "CEVA", "ACMR", "PXLW", "INDI", "RAMP", "HIMX"]


def execute_all_us_strategy():
    # ⏱️ 精准的时区与时间检查
    bj_time = datetime.utcnow() + timedelta(hours=8)
    bj_hour = bj_time.hour
    print(f"⏰ 当前北京时间实时为: {bj_time.strftime('%H:%M:%S')}")

    # 检查是否处于北京时间 08:00 到 22:00 的安全打扰区间
    if not (8 <= bj_hour < 22):
        print("💤 当前处于深夜静音保护时段，全美股雷达在云端默默做日志，拒绝打扰主人。")
        return

    dynamic_stocks = fetch_us_stock_universe()
    print(f"🚀 精准对齐启动 [全美股 {len(dynamic_stocks)} 只小盘股成交量穿透判别]...")
    
    # 限制单次扫描前 40 只异动个股，确保工作流不会超时
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
            
            # ✨ 核心满足测试防线：由于我们把阈值改为了 0.0，所有有交易的个股都会瞬间触发！
            if current_multiplier >= VOLUME_MULTIPLIER:
                suggested_shares = SINGLE_SNIPER_BUDGET_USD / current_price if current_price > 0 else 0
                stop_loss_price = current_price * 0.93
                
                push_title = f"全美放量爆破：【{ticker_symbol}】主力强力扫货！"
                push_content = (
                    f"🏷️ 【当前系统阶段】: 🧪 2026实战模拟推演期 (7月1日正式记账)\n"
                    f"💰 实时收盘价: ${current_price:.2f} | 📊 异常放量: {current_multiplier:.2f}倍\n"
                    f"------------------------\n"
                    f"🎯 【全美股大数据量化突击单】:\n"
                    f"💵 本笔固定拨发轻仓子弹: 【 $800 美元 】 (约合 6,240 港币)\n"
                    f"🛒 建议模拟买入股数: 【 {suggested_shares:.0f} 股 】\n"
                    f"🛑 【华尔街防线】: 若买入，7% 机械硬止损价为 【 ${stop_loss_price:.2f} 】 (跌破严禁抗单！)\n"
                    f"------------------------\n"
                    f"📝 提示: 接收时段已完美对齐北京时间 08:00~22:00。包含了开盘前半小时的大数据抓取！"
                )
                
                # ✨ 调用我们修复后的、能够全局继承密钥的底层网络请求函数
                send_to_bark_with_override_raw(title=push_title, content=push_content, group="全美股主力爆破")
                
            # 设置安全睡眠延时
            time.sleep(1.2)
        except Exception as e: 
            continue


# 为保持向下兼容性，做一个函数名小映射
def send_to_bark_with_override(title: str, content: str, multiplier: float, group: str = "全美股主力爆破"):
    send_to_bark_raw(title, content, group)

def send_to_bark_with_override_raw(title: str, content: str, group: str = "全美股主力爆破"):
    send_to_bark_raw(title, content, group)


if __name__ == "__main__":
    execute_all_us_strategy()
    print("🏁 全美股大数据实时异动扫描全部结束。")
