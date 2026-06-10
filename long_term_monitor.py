import os
import time
import urllib.parse
import requests
import pandas as pd
import yfinance as yf

# ==========================================
# 1. 核心参数与精简核心资产池
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")

# 你的长线专属监控标的
TICKERS = ["QQQ", "VOO", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B"]

# ==========================================
# 2. 消息通知分发管道
# ==========================================
def push_bark_notification(title: str, content: str, target_url: str = None, group: str = "长线资产加码", sound: str = "circles"):
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
# 3. 核心执行流与批量洗数
# ==========================================
def main():
    print(f"💎 启动防限流升级版长线趋势过滤，股票池: {TICKERS}")
    start_time = time.time()
    
    try:
        # ✨ 终极提速与抗封锁防线：一次请求打包全部数据，彻底规避 429 Rate Limit！
        # 显式使用 multi_level_index=False 以简化多标的 DataFrame 的纵向切割
        df_raw = yf.download(tickers=TICKERS, period="365d", auto_adjust=True, progress=False)
        
        if df_raw.empty:
            print("❌ 批量下载返回了空数据，可能雅虎服务临时震荡。")
            return
            
    except Exception as e:
        print(f"❌ 批量拉取大盘行情失败，原因: {e}")
        return

    triggered_count = 0

    # 循环穿透处理每一个 Ticker 的历史矩阵
    for ticker in TICKERS:
        try:
            # yf.download 在多股票时返回的是 MultiIndex，我们需要把单只股票的行情切片提取出来
            # 兼容处理多级列索引：提取 Close, High, Low
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_history = pd.DataFrame({
                    'Close': df_raw['Close'][ticker],
                    'High': df_raw['High'][ticker],
                    'Low': df_raw['Low'][ticker]
                }).dropna()
            else:
                # 只有一只股票时的单级索引兜底
                df_history = df_raw[['Close', 'High', 'Low']].dropna()

            if len(df_history) < 200:
                print(f"⚠️ {ticker} 历史有效 K 线不足 200 天，跳过。")
                continue
            
            # 计算技术参数
            df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
            
            # 计算 RSI 14
            delta = df_history['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            df_history['RSI_14'] = 100 - (100 / (1 + rs))
            
            # 锁定最新一天的核心切片数据
            latest_row = df_history.iloc[-1]
            price = float(latest_row['Close'])
            sma_200 = float(latest_row['SMA_200'])
            rsi_14 = float(latest_row['RSI_14'])
            
            # 计算均线偏离百分比
            bias_200 = (price / sma_200) - 1
            
            # ------------------------------------------
            # 📈 复合长线低风险区判定逻辑
            # ------------------------------------------
            # 1. 价格必须站稳在 200 日牛熊分界线上方（确保不是处于熊市阴跌中）
            # 2. 回调贴近均线（偏离度在 0% 到 4% 之内）或者 RSI 指标降至 52 以下（动能安全无泡沫）
            if price > sma_200:
                if (0 <= bias_200 <= 4.0) or (rsi_14 < 52):
                    triggered_count += 1
                    
                    push_title = f"💎 长线价值加码：【{ticker}】触发核心防御买入区！"
                    push_content = (
                        f"🏷 【定投/波段提示】: 🪐 资产处于多头牛市回踩点\n"
                        f"------------------------\n"
                        f"📊 标的数据穿透：\n"
                        f"💵 当前价格: ${price:.2f}\n"
                        f"📈 200日牛熊线: ${sma_200:.2f}\n"
                        f"🎯 均线偏离度: {bias_200:+.2f}% (进入分批吸筹区)\n"
                        f"🟢 实时 RSI(14): {rsi_14:.1f} (动能安全、非严重超买)\n"
                        f"------------------------\n"
                        f"💡 操盘策略：若满足你本月的定投额度或仓位控制，大盘指数型基金此位置具备极高安全边际，建议按计划加码。"
                    )
                    yahoo_url = f"https://yahoo.com{ticker}"
                    
                    print(f"🎯 发射加码信号: {ticker} (偏离度: {bias_200:.2f}%)")
                    push_bark_notification(title=push_title, content=push_content, target_url=yahoo_url)
                    
        except Exception as e:
            print(f"⚠️ 处理单只股票 {ticker} 时数据清洗异常: {e}")
            continue

    duration = round(time.time() - start_time, 2)
    print(f"🏁 长线监控分析全部结束。耗时: {duration} 秒。共触发加码提示: {triggered_count} 只。")

if __name__ == "__main__":
    main()
