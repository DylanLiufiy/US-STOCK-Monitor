import os
import time
import json
import random
import urllib.parse
import requests
import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types

# ==========================================
# 1. 动态资金库画像
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

MONTHLY_BUDGET = 1400.0    # 每个月新增固定定投金额 (活钱美元)
RESERVE_TOTAL = 18400.0    # 本金内部切割后，留给长线的总预备金 (本金美元)
TIME_HORIZON_MONTHS = 12.0 # 强制分散目标一整年 (12个月)

TICKERS = ["QQQ", "VOO"]   # 精简大盘组合

# ==========================================
# 2. 📡 消息通知分发管道 (手机精简短卡片推送)
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
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("📬 手机精简短卡片已成功送达终端。")
    except Exception as e:
        print(f"⚠ Bark 推送管道异常: {e}")

# ==========================================
# 3. 宏观双探针：防封锁版抓取
# ==========================================
def fetch_macro_indicators() -> tuple:
    cnn_score = 50.0
    vix_price = 18.0 
    
    # 1. 抓取 CNN 情绪分
    url = "https://cnn.io"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            cnn_score = float(res.json()['fear_and_greed']['score'])
    except:
        pass
        
    # 2. 独立轻量拉取 VIX 绝对值
    try:
        vix_ticker = yf.Ticker("^VIX")
        vix_hist = vix_ticker.history(period="1d", progress=False)
        if not vix_hist.empty:
            vix_price = float(vix_hist['Close'].iloc[-1])
    except Exception as e:
        print(f"⚠️ VIX 独立轻量探针受阻 ({e})，启用历史中位数 18.0 平稳过渡。")
        
    return cnn_score, vix_price

# ==========================================
# 4. 🧠 Google 金融大模型（抗 503 瞬时超载稳健版）
# ==========================================
def ask_google_finance_model(ticker: str, price: float, rsi: float, bias: float, cnn_score: float, vix: float) -> tuple:
    if not GOOGLE_API_KEY:
        return (65.0, 1.0, "未绑定 GOOGLE_API_KEY，启用纯技术面规则。")
        
    max_ai_retries = 3
    for attempt in range(1, max_ai_retries + 1):
        try:
            client = genai.Client(api_key=GOOGLE_API_KEY)
            t_obj = yf.Ticker(ticker)
            news_titles = [n.get('title', '') for n in t_obj.news[:2]] if t_obj.news else []
            news_context = " | ".join(news_titles) if news_titles else "暂无近两日公开突发大事件"
            
            prompt = (
                f"分析美股指数 【{ticker}】 的最新量化快照：现价 ${price:.2f}, 离200日线偏离度 {bias:+.2f}%, "
                f"RSI(14) {rsi:.1f}, CNN恐慌指数 {cnn_score}/100, VIX波动率 {vix:.2f}。新闻: {news_context}。\n"
                f"请以干净的 JSON 格式返回，格式必须为：\n"
                f'{{"win_rate": 65.5, "sentiment_multiplier": 1.1, "brief_reason": "一句话因果判断"}}'
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            res_data = json.loads(response.text)
            return float(res_data["win_rate"]), float(res_data["sentiment_multiplier"]), str(res_data["brief_reason"])
            
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_ai_retries:
                    sleep_time = attempt * 3 + random.randint(1, 3)
                    print(f"⚠️ 触发 Google 503 瞬时高压。正在执行第 {attempt} 次指数退避，等待 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)
                    continue
            print(f"⚠️ Google 模型在重试后仍异常: {e}")
            
    fallback_p = 68.0 if rsi < 45 else 62.0
    fallback_mult = 1.25 if cnn_score < 30 else 1.00
    return (fallback_p, fallback_mult, "谷歌大脑临时维护中，由系统本地技术面算法提供安全降级定投建议。")

# ==========================================
# 5. 动态资金再分配核心执行引擎
# ==========================================
def main():
    print("==================================================")
    print("🚀 启动【万能兜底防限流 + Google 大模型】长线指数雷达")
    print("==================================================")
    cnn_score, vix_index = fetch_macro_indicators()
    print(f"📡 [宏观天眼数据穿透]\n- CNN 恐慌指数得分: {cnn_score} / 100\n- 华尔街真实 VIX 指数: {vix_index:.2f}\n--------------------------------------------------")
    
    df_raw = pd.DataFrame()
    max_yf_retries = 4
    
    # 4 次批量同步大包重试防线
    for yf_attempt in range(1, max_yf_retries + 1):
        try:
            print(f"📡 正在尝试第 {yf_attempt} 次批量打包同步大盘历史矩阵...")
            df_raw = yf.download(tickers=TICKERS, period="365d", auto_adjust=True, progress=False)
            if not df_raw.empty:
                print("✅ 成功穿透雅虎限流防线，完整数据包已安全卸载！")
                break
        except Exception as e:
            print(f"⚠️ 雅虎硬核限流触发，原因: {e}")
            
        if yf_attempt < max_yf_retries:
            jitter_sleep = random.randint(4, 9)
            print(f"⏳ 正在执行随机时差伪装，静默休眠 {jitter_sleep} 秒后换枪重试...")
            time.sleep(jitter_sleep)

    triggered_count = 0

    for ticker in TICKERS:
        try:
            print(f"🔎 正在穿透洗数标的: {ticker} ...")
            
            has_history = False
            if not df_raw.empty:
                if isinstance(df_raw.columns, pd.MultiIndex) and ticker in df_raw['Close'].columns:
                    df_history = pd.DataFrame({'Close': df_raw['Close'][ticker]}).dropna()
                    if len(df_history) >= 200:
                        has_history = True
                elif not isinstance(df_raw.columns, pd.MultiIndex) and 'Close' in df_raw.columns:
                    df_history = df_raw[['Close']].dropna()
                    if len(df_history) >= 200:
                        has_history = True

            # 极速轻量单点单日数据探针兜底
            if not has_history:
                print(f"🚨 触发终极金身防线：由于雅虎全网高压封锁，{ticker} 启动轻量单点现价探针。")
                try:
                    single_t = yf.Ticker(ticker)
                    fast_df = single_t.history(period="1d", progress=False)
                    if not fast_df.empty:
                        price = float(fast_df['Close'].iloc[-1])
                        sma_200 = price / 1.12  
                        rsi_14 = 51.0          
                        bias_200 = 12.0
                        print(f"🎯 [现价探针抢救成功] 最新价格已截获: ${price:.2f} | 降级均线模拟: ${sma_200:.2f}")
                    else:
                        raise ValueError("单日单点行情返回同样为空")
                except Exception as ex:
                    print(f"❌ 终极抢救全面失败，标的 {ticker} 遭遇云端断网: {ex}")
                    continue
            else:
                df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
                delta = df_history['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                df_history['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
                
                latest_row = df_history.iloc[-1]
                price, sma_200, rsi_14 = float(latest_row['Close']), float(latest_row['SMA_200']), float(latest_row['RSI_14'])
                bias_200 = ((price / sma_200) - 1) * 100

            print(f"📝 {ticker} 技术快照 -> 现价: ${price:.2f} | 200日线: ${sma_200:.2f} | 偏离度: {bias_200:+.2f}% | RSI: {rsi_14:.1f}")

            # 策略条件拦截
            if price > sma_200 and (bias_200 <= 5.0 or rsi_14 < 53):
                triggered_count += 1
                
                google_p, google_mult, ai_reason = ask_google_finance_model(ticker, price, rsi_14, bias_200, cnn_score, vix_index)
                
                monthly_max_reserve_per_ticker = (RESERVE_TOTAL / TIME_HORIZON_MONTHS) / len(TICKERS) 
                base_cash_per_ticker = MONTHLY_BUDGET / len(TICKERS)                                  
                
                p = google_p / 100.0
                b = 2.5 
                q = 1.0 - p
                kelly_f = p - (q / b)
                half_kelly = max(0.0, kelly_f / 2)
                
                vix_booster = 1.00
                if vix_index >= 35.0: vix_booster = 1.80  
                elif vix_index >= 28.0: vix_booster = 1.45  
                elif vix_index <= 14.0: vix_booster = 0.20  
                    
                allocated_reserve = monthly_max_reserve_per_ticker * half_kelly * google_mult * vix_booster
                
                if allocated_reserve > monthly_max_reserve_per_ticker:
                    allocated_reserve = monthly_max_reserve_per_ticker
                    
                total_cash = base_cash_per_ticker + allocated_reserve
                suggested_shares = total_cash / price if price > 0 else 0
                
                # ✨ 🌟 终极语法重构：改用大括号三引号字符串，彻底消灭未闭合括号错误！ 🌟
                log_text = f"""🔥 [量化触发核心逻辑归档] - {ticker}
  |- Google AI 胜率预测: {google_p:.1f}%
  |- Google 情绪乘数: {google_mult:.2f}x
  |- 华尔街 VIX 抄底乘数: {vix_booster:.2f}x
  |- 半凯利仓位计算结果: {half_kelly*100:.2f}%
  |- 本月预算固定活钱: ${base_cash_per_ticker:.2f}
  |- 建议动用预备金本金: ${allocated_reserve:.2f}
  |- 🧠 谷歌大脑研判因果: {ai_reason}
--------------------------------------------------"""
                print(log_text, flush=True)
                
                push_title = f"🏛️ 大盘核心加码：【{ticker}】触发"
                push_content = (
                    f"🔮 AI胜率: {google_p:.1f}% | VIX乘数: {vix_booster:.1f}x\n" )
