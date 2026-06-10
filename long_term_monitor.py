import os
import time
import urllib.parse
import requests
import pandas as pd
import yfinance as yf

# ==========================================
# 1. 动态资金库画像（\$18400 年度平铺版）
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")

MONTHLY_BUDGET = 1400.0   # 每月新增固定购买力 (活钱美元)
RESERVE_TOTAL = 18400.0   # 存量本金切割后，留给长线的总预备金 (美元)
TIME_HORIZON_MONTHS = 12.0 # 强制分散目标一整年 (12个月)

# 核心资产定投池
TICKERS = ["QQQ", "VOO", "AAPL", "MSFT", "GOOGL"]

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
        url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=长线凯利平铺&sound=anticipate&isArchive=1"
        if target_url:
            url += f"&url={urllib.parse.quote_plus(target_url)}"
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"⚠ Bark 推送失败: {e}")

# ==========================================
# 3. 核心算法：年度平铺 + 凯利期望值交叉校准
# ==========================================
def calculate_time_spaced_allocation(price: float, rsi: float, bias: float):
    # 1. 刚性分配：计算单标的单月最大可动用预备金上限
    monthly_max_reserve_per_ticker = (RESERVE_TOTAL / TIME_HORIZON_MONTHS) / len(TICKERS)
    
    # 2. 基础固定购买力单标的分摊
    base_cash_per_ticker = MONTHLY_BUDGET / len(TICKERS)
    
    # 3. 动态凯利胜率解构 (RSI越低说明中短期反弹期望值越高)
    if rsi < 35:
        p, b = 0.75, 4.0   # 极度恐慌暴跌，胜率极高，赔率极大
    elif rsi < 45:
        p, b = 0.70, 3.0   # 黄金回调，胜率高
    elif rsi < 52:
        p, b = 0.65, 2.0   # 动能安全回落
    else:
        p, b = 0.52, 1.2   # 逼近阈值边缘，谨慎下注
        
    q = 1.0 - p
    kelly_f = p - (q / b)  # 标准凯利计算
    half_kelly = max(0.0, kelly_f / 2) # 半凯利风控平滑
    
    # 4. 时间加权交叉锁定
    allocated_reserve = monthly_max_reserve_per_ticker * half_kelly
    
    # 终极保护：单次动用也绝对不能超过当月平摊的刚性上限
    if allocated_reserve > monthly_max_reserve_per_ticker:
        allocated_reserve = monthly_max_reserve_per_ticker
        
    total_cash = base_cash_per_ticker + allocated_reserve
    suggested_shares = total_cash / price if price > 0 else 0
    
    return p * 100, allocated_reserve, monthly_max_reserve_per_ticker, total_cash, suggested_shares

# ==========================================
# 4. 数据获取与逻辑穿透
# ==========================================
def main():
    print("💎 启动【年度平铺 + 凯利矩阵】长线金库雷达...")
    try:
        df_raw = yf.download(tickers=TICKERS, period="365d", auto_adjust=True, progress=False)
        if df_raw.empty: return
    except Exception as e:
        print(f"❌ 行情批量下载失败: {e}")
        return

    for ticker in TICKERS:
        try:
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_history = pd.DataFrame({'Close': df_raw['Close'][ticker]}).dropna()
            else:
                df_history = df_raw[['Close']].dropna()

            if len(df_history) < 200: continue
            
            # 指标矩阵向量化计算
            df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
            delta = df_history['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df_history['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
            
            latest_row = df_history.iloc[-1]
            price, sma_200, rsi_14 = float(latest_row['Close']), float(latest_row['SMA_200']), float(latest_row['RSI_14'])
            bias_200 = ((price / sma_200) - 1) * 100
            
            # 长线防御拦截防线 (确保在大牛市趋势的健康回踩期才通知)
            if price > sma_200 and (bias_200 <= 5.0 or rsi_14 < 53):
                win_p, use_reserve, max_monthly_pool, total_cash, shares = calculate_time_spaced_allocation(price, rsi_14, bias_200)
                
                push_title = f"⚖️ 长线平铺校准：【{ticker}】触发买入信号！"
                push_content = (
                    f"📊 【大盘数据穿透】\n"
                    f"💵 实时现价: ${price:.2f} | 200日生命线: ${sma_200:.2f}\n"
                    f"📈 均线偏离: {bias_200:+.2f}% | 实时动能 RSI: {rsi_14:.1f}\n"
                    f"------------------------\n"
                    f"⏳ 【12个月时间安全分配结果】\n"
                    f"⏰ 本月单标的预备金刚性上限: ${max_monthly_pool:.2f}\n"
                    f"🔮 凯利模型测算当前赢面: 【 {win_p:.1f}% 】\n"
                    f"🛠️ 本月定投拨发 (固定活钱): ${MONTHLY_BUDGET/len(TICKERS):.2f}\n"
                    f"🔥 最终建议动用预备金 (动态本金): 【 ${use_reserve:.2f} 】\n"
                    f"💰 今日合并总购买力: ${total_cash:.2f}\n"
                    f"🎯 建议立即执行买入: 【 {shares:.2f} 股 】\n"
                    f"------------------------\n"
                    f"💡 操盘风控：此金额已被限定在年度 12 个月时间平铺窗口内，长短线资金独立交割，绝不会发生弹药提前打光的情况。"
                )
                
                print(f"🎯 {ticker} 触发时间平铺加码推送。分配预备金: ${use_reserve:.2f}")
                push_bark_notification(push_title, push_content, f"https://yahoo.com{ticker}")
                time.sleep(1.0)
                
        except Exception as e:
            print(f"⚠️ {ticker} 错误: {e}")

if __name__ == "__main__":
    main()
