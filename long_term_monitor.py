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

MONTHLY_BUDGET = 1400.0    # 🧠 每个月新增固定定投金额 (活钱美元)
RESERVE_TOTAL = 18400.0    # 🧠 本金内部切割后，留给长线的总预备金 (本金美元)
TIME_HORIZON_MONTHS = 12.0 # 🧠 强制分散目标一整年 (12个月)

# 🎯 核心大盘指数池：彻底精简，集中火力买下全美最强综合大盘与科技纳指
TICKERS = ["QQQ", "VOO"]

# ==========================================
# 2. 📡 消息通知分发管道 (核心补全：实现手机 Bark 强推送)
# ==========================================
def push_bark_notification(title: str, content: str, target_url: str = None):
    """
    一键穿透推送至手机 Bark，分组为【大盘指数凯利平铺】
    """
    if not BARK_KEY:
        print("ℹ️ 未配置 BARK_KEY，跳过手机端消息推送。")
        return
    try:
        encoded_title = urllib.parse.quote_plus(title)
        encoded_content = urllib.parse.quote_plus(content)
        # 带有专属声音 anticipate，并开启自动归档
        url = f"https://api.day.app/{BARK_KEY}/{encoded_title}/{encoded_content}?group=大盘指数凯利平铺&sound=anticipate&isArchive=1"
        if target_url:
            url += f"&url={urllib.parse.quote_plus(target_url)}"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ Bark 消息已成功送达手机端！")
        else:
            print(f"⚠️ Bark 接口返回异常状态码: {response.status_code}")
    except Exception as e:
        print(f"⚠ Bark 渠道推送失败: {e}")

# ==========================================
# 3. 宏观双探针：实时穿透获取 CNN 分数与 VIX 指数
# ==========================================
def fetch_macro_indicators() -> tuple:
    cnn_score = 50.0
    vix_price = 18.0 # 默认历史中位数
    
    # 1. 抓取 CNN 情绪
    url = "https://cnn.io"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            cnn_score = float(res.json()['fear_and_greed']['score'])
    except:
        pass
        
    # 2. 抓取实时 VIX 指数 (用雅虎抗限流批量单日包拉取 ^VIX)
    try:
        vix_df = yf.download("^VIX", period="5d", progress=False)
        if not vix_df.empty:
            vix_price = float(vix_df['Close'].iloc[-1])
    except Exception as e:
        print(f"⚠️ VIX 探针请求微震: {e}")
        
    return cnn_score, vix_price

# ==========================================
# 4. 🧠 Google 金融大模型结构化融合打分 (100% 长期全免费通道)
# ==========================================
def ask_google_finance_model(ticker: str, price: float, rsi: float, bias: float, cnn_score: float, vix: float) -> tuple:
    if not GOOGLE_API_KEY:
        print("ℹ️ 未检测到 GOOGLE_API_KEY，系统自动退化至基础阶梯期望分配。")
        return (65.0, 1.0, "未绑定谷歌云模型，启用纯技术面规则。")
    try:
        # ✨ 完美支持你的 AQ. 格式 Express 密钥
        client = genai.Client(api_key=GOOGLE_API_KEY)
        
        # 抓取个股近期的突发大事件新闻，作为谷歌多模态大模型的语义分析特征
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
            f"请记住华尔街名言：VIX高时买，VIX低时看。结合多模态情绪和历史深蹲均值回归概率，返回 JSON：\n"
            f"1. win_rate: 未来30天内，该资产在此点位反弹上涨的概率（0到100浮点数）。\n"
            f"2. sentiment_multiplier: 基于宏观的仓位控制乘数（0.0到1.5浮点数。市场极度亢奋时给0，VIX拉爆极度恐慌时给高分）。\n"
            f"3. brief_reason: 一句话（50字内，干货）解释你的大模型打分逻辑。\n\n"
            f"必须以纯 JSON 格式输出，格式必须为：\n"
            f'{{"win_rate": 65.5, "sentiment_multiplier": 1.1, "brief_reason": "原因..."}}'
        )
        
        # 🔥 换成对免费 API 渠道 100% 长期无限开放的最新 gemini-2.5-flash，彻底杜绝 403 权限越界报错
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        res_data = json.loads(response.text)
        return float(res_data["win_rate"]), float(res_data["sentiment_multiplier"]), str(res_data["brief_reason"])
    except Exception as e:
        print(f"⚠️ Google 模型网络或解析异常: {e}")
        return (60.0, 1.0, "谷歌大脑网络微震，启用平稳定投风控。")

# ==========================================
# 5. 动态资金再分配核心执行引擎
# ==========================================
def main():
    print(f"💎 启动【VIX 暴风抄底 + Google 大模型绑定版】长线指数雷达...")
    cnn_score, vix_index = fetch_macro_indicators()
    print(f"🛰️ 宏观天眼穿透完毕 -> CNN 指数: 【 {cnn_score} 】 | 华尔街实时 VIX 绝对值: 【 {vix_index:.2f} 】", flush=True)
    
    try:
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
            
            # 计算 200 日生命线与局部动能
            df_history['SMA_200'] = df_history['Close'].rolling(window=200).mean()
            delta = df_history['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            df_history['RSI_14'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
            
            latest_row = df_history.iloc[-1]
            price, sma_200, rsi_14 = float(latest_row['Close']), float(latest_row['SMA_200']), float(latest_row['RSI_14'])
            bias_200 = ((price / sma_200) - 1) * 100
            
            # 长线硬性边界：只有当大盘价格高于 200 日线，且出现正常技术回调时才触发
            if price > sma_200 and (bias_200 <= 5.0 or rsi_14 < 53):
                triggered_count += 1
                
                # 1. 调配 Google 免费 AI 模型获取核心预测打分
                google_p, google_mult, ai_reason = ask_google_finance_model(ticker, price, rsi_14, bias_200, cnn_score, vix_index)
                
                # 资金分配基数
                monthly_max_reserve_per_ticker = (RESERVE_TOTAL / TIME_HORIZON_MONTHS) / len(TICKERS) # $766.67
                base_cash_per_ticker = MONTHLY_BUDGET / len(TICKERS)                                  # $700.00
                
                # 2. 凯利公式基础转化
                p = google_p / 100.0
                b = 2.5 
                q = 1.0 - p
                kelly_f = p - (q / b)
                half_kelly = max(0.0, kelly_f / 2)
                
                # 3. 🛡️ 注入华尔街硬核 VIX 暴风抄底加速器
                vix_booster = 1.00
                if vix_index >= 35.0:
                    vix_booster = 1.80  # 💥 极度恐慌：本金暴涨 1.8 倍顶格吃肉！
                elif vix_index >= 28.0:
                    vix_booster = 1.45  # 💥 重大砸盘：本金放大 1.45 倍加速抄底！
                elif vix_index <= 14.0:
                    vix_booster = 0.20  # 🧊 泡沫期：收敛预备金，只用定投买
                    
                # 综合叠加计算最终预备金
                allocated_reserve = monthly_max_reserve_per_ticker * half_kelly * google_mult * vix_booster
                
                # 终极硬风控防线：单次动用绝对不能突破当月平摊的刚性上限
                if allocated_reserve > monthly_max_reserve_per_ticker:
                    allocated_reserve = monthly_max_reserve_per_ticker
                    
                total_cash = base_cash_per_ticker + allocated_reserve
                suggested_shares = total_cash / price if price > 0 else 0
                
                # 4. 🔥 消息强弹窗推送 (正式呼叫补全后的 Bark 管道)
                push_title = f"🏛️ 谷歌大模型校准：【{ticker}】触发防御买入区！"
                push_content = (
                    f"🧠 【Google Finance AI · 深度穿透研判】\n"
                    f"🗣 谷歌智囊判定: {ai_reason}\n"
                    f"🔮 胜率预测: {google_p:.1f}% | 谷歌情绪乘数: {google_mult:.2f}x\n"
                    f"------------------------\n"
                    f"💀 【华尔街核心 VIX 恐慌波动率加速器】\n"
                    f"🔥 实时 VIX 隐含波动率: 【 {vix_index:.2f} 】 | 加速乘数: 【 {vix_booster:.2f}x 】\n"
                    f"------------------------\n"
                    f"⏳ 【绑定钱包动作再分配结果】\n"
                    f"🛠️ 本月定投拨发 (固定活钱): ${base_cash_per_ticker:.2f}\n"
                    f"🔥 建议动用预备金 (AI与VIX校准): 【 ${allocated_reserve:.2f} 】\n"
                    f"💰 今日合并总购买力: 【 ${total_cash:.2f} 】\n"
                    f"🎯 建议立即执行买入: 【 {suggested_shares:.2f} 股 】\n"
                    f"------------------------\n"
                    f"💡 操盘风控：系统已完美融合谷歌AI与VIX暴涨加仓逻辑。波动率越高，本金抄底力度越刚猛，请在独立长线内机械化执行。"
                )
                
                print(f"🎯 {ticker} 完成 Google & VIX 绑定计算。分配预备金: ${allocated_reserve:.2f}")
                # 一键唤醒手机端雅虎财经看盘接口
                push_bark_notification(push_title, push_content, f"https://yahoo.com{ticker}")
                time.sleep(1.0)
                
        except Exception as e:
            print(f"⚠️ {ticker} 计算异常: {e}")

    print(f"🏁 扫描全部结束。")

if __name__ == "__main__":
    main()
