import os
import time
import urllib.parse
import requests
import pandas as pd
import yfinance as yf

# ==========================================
# 1. 动态资金库画像（精简指数大炮 + CNN 情绪控仓版）
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")

MONTHLY_BUDGET = 1400.0   # 🧠 每月新增固定购买力 (活钱美元)
RESERVE_TOTAL = 18400.0   # 🧠 存量本金切割后，留给长线的总预备金 (本金美元)
TIME_HORIZON_MONTHS = 12.0 # 🧠 强制分散目标一整年 (12个月)

# 🎯 核心大盘指数池：彻底抛弃个股套娃，集中火力买下全美最强综合大盘与科技纳指
TICKERS = ["QQQ", "VOO"]

# ==========================================
# 2. 实时穿透获取 CNN 贪婪恐慌指数
# ==========================================
def fetch_cnn_fear_and_greed() -> tuple:
    """
    直接请求 CNN 官方底层实时数据源 API 接口
    返回: (当前分数[0-100], 情绪分类字符串)
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            # 提取最后更新的当前贪婪恐慌分值
            current_score = float(data['fear_and_greed']['score'])
            current_rating = str(data['fear_and_greed']['rating']).strip().upper()
            return current_score, current_rating
    except Exception as e:
        print(f"⚠️ CNN 情绪 API 请求异常: {e}，系统将自动启用中性情绪进行平稳过渡。")
    return 50.0, "NEUTRAL"

# ==========================================
# 3. 消息通知分发管道
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
# 4. 核心算法：时间平铺 + 凯利矩阵 + CNN 情绪交叉乘数
# ==========================================
def calculate_cnn_hybrid_allocation(price: float, rsi: float, bias: float, cnn_score: float):
    # 1. 刚性时间分配：单标的单月最大可动用预备金上限
    monthly_max_reserve_per_ticker = (RESERVE_TOTAL / TIME_HORIZON_MONTHS) / len(TICKERS)
    
    # 2. 基础固定购买力单标的分摊自动升级至 700 美元
    base_cash_per_ticker = MONTHLY_BUDGET / len(TICKERS)
    
    # 3. 动态凯利胜率解构 (单指数局部维度)
    if rsi < 35:
        p, b = 0.78, 4.0   
    elif rsi < 45:
        p, b = 0.72, 3.0   
    elif rsi < 52:
        p, b = 0.65, 2.0   
    else:
        p, b = 0.52, 1.2   
        
    q = 1.0 - p
    kelly_f = p - (q / b)  
    half_kelly = max(0.0, kelly_f / 2) 
    
    # 基础动态预备金初步计算
    allocated_reserve = monthly_max_reserve_per_ticker * half_kelly
    
    # 4. 💎 核心升级：融入 CNN 贪婪恐慌指数动态乘数矩阵
    # 巴菲特法则：别人恐慌我贪婪。全市场越是极度恐慌，我们越要在时间窗口内倾泻预备金子弹。
    if cnn_score <= 25.0:
        sentiment_multiplier = 1.45  # 🔴 极端恐慌：资金权重直接放大 1.45 倍疯狂抄底！
    elif cnn_score <= 45.0:
        sentiment_multiplier = 1.15  # 🟠 恐慌：适当放大攻击火力
    elif cnn_score >= 75.0:
        sentiment_multiplier = 0.0   # 🟢 极度贪婪：触发全市场熔断机制！拒绝用任何预备金去给市场接盘
    elif cnn_score >= 55.0:
        sentiment_multiplier = 0.60   # 🟡 比较贪婪：削减预备金规模，保护本金
    else:
        sentiment_multiplier = 1.00   # ⚪ 中性情绪：保持原有凯利模型输出
        
    # 执行宏观情绪加权
    allocated_reserve = allocated_reserve * sentiment_multiplier
    
    # 终极硬风控防线：即使乘数放大，单次动用也绝对不能突破当月平摊的刚性上限上限
    if allocated_reserve > monthly_max_reserve_per_ticker:
        allocated_reserve = monthly_max_reserve_per_ticker
        
    total_cash = base_cash_per_ticker + allocated_reserve
    suggested_shares = total_cash / price if price > 0 else 0
    
    return p * 100, allocated_reserve, monthly_max_reserve_per_ticker, sentiment_multiplier, total_cash, suggested_shares

# ==========================================
# 5. 主运行逻辑
# ==========================================
def main():
    print(f"💎 启动【CNN 情绪交叉乘数 + 大盘大炮版】长线雷达，锁定目标: {TICKERS}")
    
    # 1. 拦截抓取 CNN 实时大盘情绪
    cnn_score, cnn_rating = fetch_cnn_fear_and_greed()
    print(f"🛰️ 实时宏观情绪穿透完毕：CNN 恐慌指数当前得分为 【 {cnn_score} / 100 】 | 分类标签: 【 {cnn_rating} 】", flush=True)

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
            
            # 长线牛熊生命线与局部动能计算
            df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
            delta = df_history['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df_history['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
            
            latest_row = df_history.iloc[-1]
            price, sma_200, rsi_14 = float(latest_row['Close']), float(latest_row['SMA_200']), float(latest_row['RSI_14'])
            bias_200 = ((price / sma_200) - 1) * 100
            
            # 严格的长线牛市回调拦截条件
            if price > sma_200 and (bias_200 <= 5.0 or rsi_14 < 53):
                triggered_count += 1
                
                # 调配融合了 CNN 情绪因子的核心计算引擎
                win_p, use_reserve, max_monthly_pool, mult, total_cash, shares = calculate_cnn_hybrid_allocation(price, rsi_14, bias_200, cnn_score)
                
                push_title = f"🏛️ 情绪交叉加码：【{ticker}】触发黄金防守区！"
                push_content = (
                    f"🎭 【CNN 宏观情绪大盘测谎仪】\n"
                    f"🎯 实时贪婪恐慌分值: 【 {cnn_score} / 100 】({cnn_rating})\n"
                    f"⚡ 情绪动态资金乘数: 【 {mult:.2f}x 】\n"
                    f"------------------------\n"
                    f"📊 【标的局部技术透视】\n"
                    f"💵 最新现价: ${price:.2f} | 200日均线: ${sma_200:.2f}\n"
                    f"📈 均线偏离: {bias_200:+.2f}% | 局部 RSI: {rsi_14:.1f}\n"
                    f"------------------------\n"
                    f"⏳ 【资金再分配精算结果】\n"
                    f"⏰ 本月可用预备金上限: ${max_monthly_pool:.2f}\n"
                    f"🛠️ 本月定投拨发 (固定活钱): ${MONTHLY_BUDGET/len(TICKERS):.2f}\n"
                    f"🔥 最终拨发预备金 (情绪校准): 【 ${use_reserve:.2f} 】\n"
                    f"💰 今日合并总购买力: 【 ${total_cash:.2f} 】\n"
                    f"🎯 建议立即执行买入: 【 {shares:.2f} 股 】\n"
                    f"------------------------\n"
                    f"💡 操盘提示：此配置已由局部技术面与全美宏观情绪交叉校准，在市场情绪极度悲观时加大了建仓权重，赔率极高，请机械化执行。"
                )
                
                print(f"🎯 {ticker} 触发情绪交叉加码推送。分配预备金: ${use_reserve:.2f}")
                push_bark_notification(push_title, push_content, f"https://yahoo.com{ticker}")
                time.sleep(1.0)
                
        except Exception as e:
            print(f"⚠️ {ticker} 处理异常: {e}")

    print(f"🏁 本次指数扫描结束。共触发加码提示: {triggered_count} 只。")

if __name__ == "__main__":
    main()
