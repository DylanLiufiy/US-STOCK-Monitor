import os
import time
import urllib.parse
import requests
import pandas as pd
import yfinance as yf

# ==========================================
# 1. 动态资金库画像（精简指数大炮版）
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")

MONTHLY_BUDGET = 1400.0   # 🧠 每月新增固定购买力 (活钱美元)
RESERVE_TOTAL = 18400.0   # 🧠 存量本金切割后，留给长线的总预备金 (本金美元)
TIME_HORIZON_MONTHS = 12.0 # 🧠 强制分散目标一整年 (12个月)

# 🎯 核心大盘指数池：彻底抛弃个股套娃，集中火力买下全美最顶尖的综合大盘与科技纳指
TICKERS = ["QQQ", "VOO"]

# ==========================================
# 2. 消息通知分发管道
# ==========================================
def push_bark_notification(title: str, content: str, target_url: str = None):
    if not BARK_KEY:
        print("ℹ️ 未配置 BARK_KEY，跳过手机端消息推送。")
        return
    try:
        encoded_title = urllib.parse.quote_plus(title)
        encoded_content = urllib.parse.quote_plus(content)
        url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=大盘指数凯利平铺&sound=anticipate&isArchive=1"
        if target_url:
            url += f"&url={urllib.parse.quote_plus(target_url)}"
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"⚠ Bark 推送失败: {e}")

# ==========================================
# 3. 核心算法：时间平铺 + 凯利期望值交叉校准
# ==========================================
def calculate_time_spaced_allocation(price: float, rsi: float, bias: float):
    # 1. 刚性分配：由于标的从 5 只精简到 2 只，单标的单月最大可动用预备金上限自动飙升至 766.67 美元
    monthly_max_reserve_per_ticker = (RESERVE_TOTAL / TIME_HORIZON_MONTHS) / len(TICKERS)
    
    # 2. 基础固定购买力单标的分摊自动升级至 700 美元
    base_cash_per_ticker = MONTHLY_BUDGET / len(TICKERS)
    
    # 3. 动态凯利胜率解构 (根据大盘指数的历史分位概率校准)
    if rsi < 35:
        p, b = 0.78, 4.0   # 标普/纳指极罕见大暴跌，指数必定回归，胜率极高
    elif rsi < 45:
        p, b = 0.72, 3.0   # 黄金回踩点
    elif rsi < 52:
        p, b = 0.65, 2.0   # 正常回调
    else:
        p, b = 0.52, 1.2   # 阈值边缘，极轻微加仓
        
    q = 1.0 - p
    kelly_f = p - (q / b)  # 标准凯利期望值计算
    half_kelly = max(0.0, kelly_f / 2) # 半凯利风控
    
    # 4. 时间加权交叉锁定当天的动态预备金
    allocated_reserve = monthly_max_reserve_per_ticker * half_kelly
    
    # 终极保护：单次动用绝对不能突破当月平摊的刚性上限
    if allocated_reserve > monthly_max_reserve_per_ticker:
        allocated_reserve = monthly_max_reserve_per_ticker
        
    total_cash = base_cash_per_ticker + allocated_reserve
    suggested_shares = total_cash / price if price > 0 else 0
    
    return p * 100, allocated_reserve, monthly_max_reserve_per_ticker, total_cash, suggested_shares

# ==========================================
# 4. 数据获取与逻辑穿透
# ==========================================
def main():
    print(f"💎 启动【大盘指数全景复利版】长线雷达，当前锁定标的: {TICKERS}")
    try:
        # 抗限流单次批量打包拉取
        df_raw = yf.download(tickers=TICKERS, period="365d", auto_adjust=True, progress=False)
        if df_raw.empty: return
    except Exception as e:
        print(f"❌ 行情批量下载失败: {e}")
        return

    triggered_count = 0

    for ticker in TICKERS:
        try:
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_history = pd.DataFrame({'Close': df_raw['Close'][ticker]}).dropna()
            else:
                df_history = df_raw[['Close']].dropna()

            if len(df_history) < 200: continue
            
            # 200日长线牛熊生命线
            df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
            
            # RSI 14 动能出清清洗
            delta = df_history['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df_history['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
            
            latest_row = df_history.iloc[-1]
            price, sma_200, rsi_14 = float(latest_row['Close']), float(latest_row['SMA_200']), float(latest_row['RSI_14'])
            bias_200 = ((price / sma_200) - 1) * 100
            
            # 严格的长线牛市回调拦截条件（价格高于200日线 且 偏离度低或RSI安全）
            if price > sma_200 and (bias_200 <= 5.0 or rsi_14 < 53):
                triggered_count += 1
                
                # 调配重构后的时间-空间交叉算法引擎
                win_p, use_reserve, max_monthly_pool, total_cash, shares = calculate_time_spaced_allocation(price, rsi_14, bias_200)
                
                push_title = f"🏛️ 大盘指数加码：【{ticker}】触发黄金防守区！"
                push_content = (
                    f"📊 【大盘实时数据】\n"
                    f"💵 最新价格: ${price:.2f} | 200日生命线: ${sma_200:.2f}\n"
                    f"📈 均线偏离: {bias_200:+.2f}% | 实时动能 RSI: {rsi_14:.1f}\n"
                    f"------------------------\n"
                    f"⏳ 【12个月时间平铺精算结果】\n"
                    f"⏰ 本月该指数可用预备金上限: ${max_monthly_pool:.2f}\n"
                    f"🔮 凯利公式测算当前赢面: 【 {win_p:.1f}% 】\n"
                    f"🛠️ 本月定投拨发 (固定活钱): ${MONTHLY_BUDGET/len(TICKERS):.2f}\n"
                    f"🔥 最终建议动用预备金 (动态本金): 【 ${use_reserve:.2f} 】\n"
                    f"💰 今日合并总购买力: 【 ${total_cash:.2f} 】\n"
                    f"🎯 建议立即执行买入: 【 {shares:.2f} 股 】\n"
                    f"------------------------\n"
                    f"💡 操盘提示：个股已被完全剥离，当前资金以高胜率重炮火力集中轰击全美最强指数。请无脑按照建议股数执行定投。"
                )
                
                print(f"🎯 {ticker} 触发指数平铺加码推送。分配预备金: ${use_reserve:.2f}")
                push_bark_notification(push_title, push_content, f"https://yahoo.com{ticker}")
                time.sleep(1.0)
                
        except Exception as e:
            print(f"⚠️ {ticker} 处理异常: {e}")

    print(f"🏁 本次指数扫描结束。共触发加码提示: {triggered_count} 只。")

if __name__ == "__main__":
    main()
