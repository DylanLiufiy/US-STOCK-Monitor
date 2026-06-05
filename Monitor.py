import os
import sys
from datetime import datetime
import requests
import yfinance as yf

# ============================================================================
# 核心配置：定义监控标的及其【个性化回调报警区间】(min_drop, max_drop)
# VOO等指数通常跌5%就是极好买点；QQQ与普通科技股维持5%-10%；高波动成长股可调宽
# ============================================================================
MONITOR_POOL = {
    # 0. 核心指数大盘（防守稳健，分级监控）
    "VOO": {"name": "标普500-ETF", "min": 5.0, "max": 10.0},     # VOO达到5%即属于强买入信号
    "QQQ": {"name": "纳指100-ETF", "min": 5.0, "max": 10.0},     # QQQ维持经典中长线回调区间
    
    # 1. 传统七姐妹（核心蓝筹巨头）
    "AAPL": {"name": "苹果", "min": 5.0, "max": 10.0},
    "MSFT": {"name": "微软", "min": 5.0, "max": 10.0},
    "NVDA": {"name": "英伟达", "min": 5.0, "max": 10.0},
    "GOOGL": {"name": "谷歌", "min": 5.0, "max": 10.0},
    "AMZN": {"name": "亚马逊", "min": 5.0, "max": 10.0},
    "META": {"name": "Meta", "min": 5.0, "max": 10.0},
    "TSLA": {"name": "特斯拉", "min": 6.0, "max": 12.0},       # 特斯拉波动大，报警线轻微调宽
    
    # 2. 2026 算力/半导体核心黑马
    "AVGO": {"name": "博通", "min": 5.0, "max": 10.0},
    "MU": {"name": "美光科技", "min": 6.0, "max": 12.0},
    "ASML": {"name": "阿斯麦", "min": 5.0, "max": 10.0},
    "LRCX": {"name": "泛林集团", "min": 5.0, "max": 10.0},
    
    # 3. AI软件、生物医药与硬科技
    "PLTR": {"name": "Palantir", "min": 6.0, "max": 12.0},     # 高弹性，给更深的抄底空间
    "CRM": {"name": "Salesforce", "min": 5.0, "max": 10.0},
    "LLY": {"name": "礼来", "min": 5.0, "max": 10.0},
    "RKLB": {"name": "Rocket Lab", "min": 7.0, "max": 15.0}    # 极高Beta航天股，7%以上才报警
}

# 从 GitHub Secrets 中安全读取微信推送 Key
SERVER_CHAN_KEY = os.environ.get("SERVER_CHAN_KEY")

def send_notification(title, content):
    if not SERVER_CHAN_KEY:
        print("未配置 SERVER_CHAN_KEY，取消发送")
        return
    url = f"https://ftqq.com{SERVER_CHAN_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        requests.post(url, data=data)
        print(f"【已发送提醒】: {title}")
    except Exception as e:
        print(f"发送消息失败: {e}")

def check_drawdown():
    print(f"=== 开始执行美股多策略分级监控 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    alert_triggered = False

    for ticker, config in MONITOR_POOL.items():
        name = config["name"]
        min_drop = config["min"]
        max_drop = config["max"]
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="60d")
            if df.empty:
                continue

            # 寻找过去 30 个交易日的近期最高锚定点
            recent_high = df["High"].tail(30).max()
            current_price = df["Close"].iloc[-1]
            drawdown = (recent_high - current_price) / recent_high * 100

            print(f"[{ticker}] {name}: 30日高点 ${recent_high:.2f} | 当前 ${current_price:.2f} | 当前回撤: -{drawdown:.2f}% (报警区间: {min_drop}%~{max_drop}%)")

            # 触发个股自定义的凯利补仓线
            if min_drop <= drawdown <= max_drop:
                alert_triggered = True
                title = f"🚨 凯利加仓信号：{name}({ticker}) 已回调 {drawdown:.1f}%"
                content = (
                    f"### 🎯 触发【{min_drop}% ~ {max_drop}%】独立量化抄底线\n\n"
                    f"- **监控标的**: {name} ({ticker})\n"
                    f"- **近30日最高点**: `${recent_high:.2f}`\n"
                    f"- **实时当前最新价**: `${current_price:.2f}`\n"
                    f"- **当前相对回调幅度**: `-{drawdown:.2f}%`\n\n"
                    f"💡 **实战投资建议**：\n"
                    f"该标的已进入为你量身定制的凯利公式低吸区间。请检查你 3万美元 的后备金，准备按照分批金字塔逻辑挂单建仓。"
                )
                send_notification(title, content)
        except Exception as e:
            print(f"获取 {ticker} 实时数据失败: {e}")

    if not alert_triggered:
        print("目前盘中没有任何资产触及设定的加仓线，系统继续保持静默。")

if __name__ == "__main__":
    check_drawdown()
