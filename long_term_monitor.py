import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import requests
import pandas as pd
import yfinance as yf

# ==========================================
# 1. 配置参数与专属股票池
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")

# 你的专属核心资产池：加入核心指数 QQQ、VOO 以及你关心的长线大蓝筹
TICKERS = [
    "QQQ", "VOO", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B"
]

MAX_WORKERS = 5       # 长线池较小，5个并发足够
MAX_RETRIES = 3       # 失败重试次数
BACK_DAYS = 365       # 历史数据天数

# ==========================================
# 2. 核心量化指标计算
# ==========================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算长线 200日均线与 RSI，采用后复权价 Adj Close
    """
    if df.empty or len(df) < 200:
        return df
        
    # 计算 200日简单移动平均线 (SMA 200)
    df['SMA_200'] = df['Adj Close'].rolling(window=200).mean()
    
    # 计算 14日 RSI
    delta = df['Adj Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    return df

# ==========================================
# 3. 消息通知分发管道
# ==========================================
def push_bark_notification(title: str, content: str, target_url: str = None, group: str = "长线资产加码", sound: str = "circles"):
    """
    一键推送消息到手机 Bark
    """
    if not BARK_KEY:
        print("ℹ️ 未配置 BARK_KEY，跳过手机端消息推送。")
        return
    try:
        encoded_title = urllib.parse.quote_plus(title)
        encoded_content = urllib.parse.quote_plus(content)
        url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group={group}&sound={sound}&isArchive=1"
        if target_url:
            url += f"&url={urllib.parse.quote_plus(target_url)}"
            
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"⚠ Bark 长线推送失败: {e}")

# ==========================================
# 4. 单股长线价值穿透
# ==========================================
def process_long_term_stock(ticker: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            pe_ratio = info.get('trailingPE', None)
            current_price = info.get('currentPrice', None)
            
            df_history = ticker_obj.history(period=f"{BACK_DAYS}d")
            if df_history.empty or len(df_history) < 200:
                return None
                
            df_history = calculate_indicators(df_history)
            latest_row = df_history.iloc[-1]
            
            price = current_price if current_price else latest_row['Adj Close']
            sma_200 = latest_row['SMA_200']
            rsi_14 = latest_row['RSI_14']
            
            if pd.isna(sma_200) or pd.isna(rsi_14):
                return None
                
            # 计算现价偏离 200 日均线的比例 (例如：1.03 代表比均线高 3%)
            bias_200 = (price / sma_200) - 1
            
            return {
                "ticker": ticker,
                "price": round(price, 2),
                "sma_200": round(sma_200, 2),
                "rsi_14": round(rsi_14, 2),
                "pe_ratio": round(pe_ratio, 2) if pe_ratio else "N/A",
                "bias_200": round(bias_200 * 100, 2) # 百分比化
            }
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"⚠ {ticker} 长线计算异常: {e}")
                return None
            time.sleep(1.0 * attempt)
    return None

# ==========================================
# 5. 调度与核心过滤策略
# ==========================================
def main():
    print(f"💎 开启核心资产长线趋势过滤，总数: {len(TICKERS)} 只...")
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(process_long_term_stock, t): t for t in TICKERS}
        for future in as_completed(future_to_ticker):
            res = future.result()
            if res:
                results.append(res)
                
    if not results:
        print("❌ 未能成功获取到任何核心资产行情。")
        return
        
    triggered_signals = []
    
    for item in results:
        t = item["ticker"]
        p = item["price"]
        sma = item["sma_200"]
        rsi = item["rsi_14"]
        bias = item["bias_200"]
        pe = item["pe_ratio"]
        
        # ------------------------------------------
        # 📈 长线核心量化加码金标（回踩加长线多头）
        # ------------------------------------------
        # 指标逻辑：对于大盘ETF(QQQ/VOO)，只要维持在SMA200上方多头趋势(bias > 0)
        # 且回踩贴近均线(bias <= 4%)，或者中线RSI超卖健康回落(RSI < 52)，即为绝佳定投分批建仓眼位！
        if p > sma:
            if (0 <= bias <= 4.0) or (rsi < 52):
                triggered_signals.append(item)
                
                # 触发 Bark 强通知提示你是否买入
                push_title = f"💎 长线价值加码：【{t}】触发核心防御买入区！"
                push_content = (
                    f"🏷 【定投/波段提示】: 🪐 资产处于多头牛市回踩点\n"
                    f"------------------------\n"
                    f"📊 标的数据穿透：\n"
                    f"💵 当前价格: ${p:.2f}\n"
                    f"📈 200日牛熊线: ${sma:.2f}\n"
                    f"🎯 均线偏离度: {bias:+.2f}% (完美契合分批吸筹区)\n"
                    f"🟢 实时 RSI(14): {rsi:.1f} (动能指标安全、非超买)\n"
                    f"🏛 历史估值 PE: {pe}\n"
                    f"------------------------\n"
                    f"💡 操盘策略：若满足你本月的定投额度或仓位控制，大盘指数型基金此位置具备极高安全边际，建议按计划加码。"
                )
                yahoo_url = f"https://yahoo.com{t}"
                
                print(f"🎯 发射加码信号: {t} (偏离度: {bias}%)")
                push_bark_notification(title=push_title, content=push_content, target_url=yahoo_url)
                time.sleep(1.0)
                
    # 无论有无信号触发，依然留存本地大盘大卡片看板
    if not triggered_signals:
        print("🟢 今日大盘及长线核心资产处于高位运行或未跌入买入区间，长线雷达保持静默。")

if __name__ == "__main__":
    main()
