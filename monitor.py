import os
import sys
import time
import urllib.parse
import requests
import yfinance as yf

# ==================== 安全与策略配置区域 ====================
# 🔒 自动读取 GitHub Secrets 安全保险箱中的 Bark 密钥
BARK_KEY = os.environ.get("BARK_KEY")

# 🎯 监控目标池：涵盖您之前的大票，以及 Serenity 点名的高弹性潜力瓶颈股
# 注：Sivers (SIVE.ST) 和 X-FAB (XFAB.PA) 为欧洲本土主板，美股对应 ADR 为 SIVNY 和 XFABF
MONITOR_STOCKS = [
    "AXTI", "SIVNY", "XFABF", "WOLF", "VICR", "AAOI",  # Serenity 1-30亿硬核卡点股
    "GOOG", "NVDA", "MU"                              # 之前聊过的核心科技大票
]

# 📊 过滤器动态阈值设定
MARKET_CAP_MIN = 100_000_000      # 市值下限：1亿美元
MARKET_CAP_MAX = 3_000_000_000    # 市值上限：30亿美元
VOLUME_MULTIPLIER = 3.0           # 成交量爆破阈值：30天均值的 3.0 倍
# ============================================================


def send_to_bark(title: str, content: str, group: str = "美股量化系统"):
    """
    Bark 生产环境安全发送模块
    """
    if not BARK_KEY:
        print(f"⚠️ 未检测到 BARK_KEY，本地打印控制台 -> 【{title}】: {content}")
        return

    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)

    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=electronic"
    
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            print(f"🔔 成功推送 Bark 通知：{title}")
        else:
            print(f"❌ Bark 推送失败，HTTP 状态码: {res.status_code}")
    except Exception as e:
        print(f"❌ 推送由于网络异常失败: {e}")


def execute_serenity_strategy():
    """
    核心量化策略：市值过滤 + 30日成交量3倍暴破捕获
    """
    print("🚀 启动 [Serenity 瓶颈股异动扫描系统]...")
    
    for ticker_symbol in MONITOR_STOCKS:
        try:
            print(f"⏳ 正在深度解构标的: {ticker_symbol} ...")
            ticker = yf.Ticker(ticker_symbol)
            
            # 1. 抓取基本面市值数据
            info = ticker.info
            market_cap = info.get("marketCap", 0)
            
            # 如果市值不在 1亿 ~ 30亿美元 范围内，直接战略放弃（大票或过小的微盘垃圾股）
            if not (MARKET_CAP_MIN <= market_cap <= MARKET_CAP_MAX):
                print(f"   ℹ️ 跳过 {ticker_symbol}: 当前市值 ${market_cap:,.0f} 不在 1亿-30亿 核心选股区间。")
                continue
                
            # 2. 抓取过去 35 天的历史 K 线（确保有足额 30 个交易日计算均值）
            hist = ticker.history(period="35d")
            if len(hist) < 31:
                print(f"   ⚠️ 跳过 {ticker_symbol}: 历史数据不足 30 天，无法计算均值。")
                continue
                
            # 3. 计算量化指标
            # 取出最新的今日成交量，以及前 30 天的历史成交量序列
            today_volume = hist['Volume'].iloc[-1]
            past_30_days_volume = hist['Volume'].iloc[-31:-1]
            avg_volume_30d = past_30_days_volume.mean()
            
            # 计算当前成交量相较于均值的倍数
            current_multiplier = today_volume / avg_volume_30d if avg_volume_30d > 0 else 0
            
            print(f"   📊 检查完毕 -> 今日量: {today_volume:,.0f} | 30天均量: {avg_volume_30d:,.0f} | 当前倍数: {current_multiplier:.2f}x")
            
            # 4. 判断是否触发 3 倍爆破信号
            if current_multiplier >= VOLUME_MULTIPLIER:
                current_price = hist['Close'].iloc[-1]
                
                push_title = f"🚨 核心爆破：【{ticker_symbol}】主力资金疯狂扫货！"
                push_content = (
                    f"💡 触发原因: 符合 Serenity 瓶颈选股逻辑\n"
                    f"💰 当前价格: ${current_price:.2f}\n"
                    f"🏢 股票市值: ${market_cap/1_000_000:.1f}M (符合1-30亿标准)\n"
                    f"📈 成交量增幅: 达到 30天均值的 {current_multiplier:.2f} 倍 (超 3 倍阈值)"
                )
                
                # 发送高危特制 Bark 通道
                send_to_bark(title=push_title, content=push_content, group="Serenity冷门爆款")
                
            time.sleep(1) # 策略防封锁延迟
            
        except Exception as e:
            print(f"❌ 处理标的 {ticker_symbol} 时发生异常: {e}")


if __name__ == "__main__":
    execute_serenity_strategy()
    print("🏁 全自动化策略异动扫描完成。")
