import os
import time
import json
import urllib.parse
import requests
import pandas as pd
import yfinance as yf
from google import genai
from google.genai import types

# ==========================================
# 1. 动态资金库画像（Google 免费API绑定版）
# ==========================================
BARK_KEY = os.environ.get("BARK_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

MONTHLY_BUDGET = 1400.0    # 每月新增固定定投金额 (活钱美元)
RESERVE_TOTAL = 18400.0    # 本金内部切割后，留给长线的总预备金 (本金美元)
TIME_HORIZON_MONTHS = 12.0 # 强制分散目标一整年 (12个月)

TICKERS = ["QQQ", "VOO"]

# ==========================================
# 2. 📡 消息通知分发管道 (手机精简战术短推送)
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
# 3. 宏观双探针：实时穿透获取 CNN 分数与 VIX 指数
# ==========================================
def fetch_macro_indicators() -> tuple:
    cnn_score = 50.0
    vix_price = 18.0 
    url = "https://cnn.io"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            cnn_score = float(res.json()['fear_and_greed']['score'])
    except:
        pass
    try:
        vix_df = yf.download("^VIX", period="5d", progress=False)
        if not vix_df.empty:
            vix_price = float(vix_df['Close'].iloc[-1])
    except Exception as e:
        print(f"⚠️ VIX 探针请求微震: {e}")
    return cnn_score, vix_price

# ==========================================
# 4. 🧠 Google 金融大模型（带指数级自动退避重试，死磕 503）
# ==========================================
def ask_google_finance_model(ticker: str, price: float, rsi: float, bias: float, cnn_score: float, vix: float) -> tuple:
    if not GOOGLE_API_KEY:
        return (65.0, 1.0, "未绑定 GOOGLE_API_KEY，启用纯技术面规则。")
        
    # ✨ 🌟 核心改进 1：设计 3 次硬核指数级退避重试，强行碾压 503 暂态高峰 🌟
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            client = genai.Client(api_key=GOOGLE_API_KEY)
            t_obj = yf.Ticker(ticker)
            news_titles = [n.get('title', '') for n in t_obj.news[:3]] if t_obj.news else []
            news_context = " | ".join(news_titles) if news_titles else "暂无近两日公开突发大事件"
            
            prompt = (
                f"你现在是部署在量化基金底层的 Google Finance AI 核心预测大脑。 "
                f"请综合分析美股核心指数 【{ticker}】 的以下最新量化快照：\n"
                f"- 当前实时现价: ${price:.2f}\n"
                f"- 离200日均线物理偏离度: {bias:+.2f}%\n"
                f"- 局部动能指标 RSI(14): {rsi:.1f}\n"
                f"- 全美宏观 CNN 贪婪恐慌指数: {cnn_score}/100\n"
                f"- 华尔街核心 VIX 恐慌波动率指数: {vix:.2f}\n"
                f"- 该指数突发新闻流: {news_context}\n\n"
                f"请返回 JSON：\n"
                f"1. win_rate: 未来30天内，该资产在此点位反弹上涨的概率（0到100浮点数）。\n"
                f"2. sentiment_multiplier: 基于宏观的仓位控制乘数（0.0到1.5浮点数）。\n"
                f"3. brief_reason: 一句话（50字内，干货）解释你的大模型打分逻辑。\n\n"
                f"必须以纯 JSON 格式输出，格式必须为：\n"
                f'{{"win_rate": 65.5, "sentiment_multiplier": 1.1, "brief_reason": "原因..."}}'
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            res_data = json.loads(response.text)
            return float(res_data["win_rate"]), float(res_data["sentiment_multiplier"]), str(res_data["brief_reason"])
            
        except Exception as e:
            # 判断是否为谷歌服务器超载
            if "503" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < max_retries:
                    sleep_time = 2 ** attempt  # 第一次等2秒，第二次等4秒
                    print(f"⚠️ 触发 Google 503 瞬时高压拦截。正在执行第 {attempt} 次指数退避，静默等待 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)
                    continue
            print(f"⚠️ Google 模型在重试 {max_retries} 次后仍解析异常: {e}")
            
    # ✨ 🌟 核心改进 2：优雅降级。如果谷歌服务器彻底瘫痪，根据技术面参数自动吐出科学的期望打分，绝不断流！ 🌟
    print("🚨 [系统风控保护] 谷歌大脑完全不可用，系统启动纯技术面规则进行安全降级衔接。")
    fallback_p = 68.0 if rsi < 45 else 62.0
    fallback_mult = 1.25 if cnn_score < 30 else 1.00
    return (fallback_p, fallback_mult, "谷歌大脑临时维护中，由系统本地技术面算法提供安全降级定投建议。")

# ==========================================
# 5. 动态资金再分配核心执行引擎
# ==========================================
def main():
    print(f"==================================================\n🚀 启动【VIX 暴风抄底 + Google 大模型】长线指数雷达\n==================================================")
    cnn_score, vix_index = fetch_macro_indicators()
    print(f"📡 [宏观天眼数据穿透]\n- CNN 恐慌指数得分: {cnn_score} / 100\n- 华尔街真实 VIX 指数: {vix_index:.2f}\n--------------------------------------------------", flush=True)
    
    try:
        df_raw = yf.download(tickers=TICKERS, period="365d", auto_adjust=True, progress=False)
        if df_raw.empty: return
    except Exception as e:
        print(f"❌ 行情批量下载失败: {e}")
        return

    triggered_count = 0

    for ticker in TICKERS:
        try:
            print(f"🔎 正在穿透洗数标的: {ticker} ...")
            if isinstance(df_raw.columns, pd.MultiIndex):
                df_history = pd.DataFrame({'Close': df_raw['Close'][ticker]}).dropna()
            else:
                df_history = df_raw[['Close']].dropna()

            if len(df_history) < 200: 
                print(f"⚠️ {ticker} 历史 K 线不足 200 天，安全跳过。")
                continue
            
            df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
            delta = df_history['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df_history['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
            
            latest_row = df_history.iloc[-1]
            price, sma_200, rsi_14 = float(latest_row['Close']), float(latest_row['SMA_200']), float(latest_row['RSI_14'])
            bias_200 = ((price / sma_200) - 1) * 100
            
            print(f"📝 {ticker} 技术快照 -> 现价: ${price:.2f} | 200日线: ${sma_200:.2f} | 偏离度: {bias_200:+.2f}% | RSI: {rsi_14:.1f}")

            if price > sma_200 and (bias_200 <= 5.0 or rsi_14 < 53):
                triggered_count += 1
                
                # 调配加固后的 Google AI 模型获取核心多模态预测
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
                
                print(f"🔥 [量化触发核心逻辑归档] - {ticker}\n"
                      f"  |- Google AI 胜率预测: {google_p:.1f}%\n"
                      f"  |- Google 情绪乘数: {google_mult:.2f}x\n"
                      f"  |- 华尔街 VIX 抄底乘数: {vix_booster:.2f}x\n"
                      f"  |- 半凯利仓位计算结果: {half_kelly*100:.2f}%\n"
                      f"  |- 本月预算固定活钱: ${base_cash_per_ticker:.2f}\n"
                      f"  |- 建议动用预备金本金: ${allocated_reserve:.2f}\n"
                      f"  |- 🧠 谷歌大脑全文本研判因果: {ai_reason}\n"
                      f"--------------------------------------------------", flush=True)
                
                push_title = f"🏛️ 大盘核心加码：【{ticker}】触发"
                push_content = (
                    f"🔮 AI胜率: {google_p:.1f}% | VIX乘数: {vix_booster:.1f}x\n"
                    f"💵 预备金本金: +${allocated_reserve:.2f}\n"
                    f"💰 今日合并购买力: 【 ${total_cash:.2f} 】\n"
                    f"🎯 建议立即建仓执行: 【 {suggested_shares:.2f} 股 】\n"
                    f"🧠 核心逻辑: {ai_reason}"
                )
                push_bark_notification(push_title, push_content, f"https://yahoo.com{ticker}")
                time.sleep(1.0)
            else:
                print(f"🟢 {ticker} 处于高位运行，暂未跌入量化买入盲区。")
                
        except Exception as e:
            print(f"⚠️ {ticker} 绑定计算异常: {e}")

    print(f"==================================================\n🏁 长线指数扫描全部结束。共触发加码提示: {triggered_count} 只。\n==================================================")

if __name__ == "__main__":
    main()
