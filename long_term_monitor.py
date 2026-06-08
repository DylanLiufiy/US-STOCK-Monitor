import os
import sys
import time
import urllib.parse
import requests
import yfinance as yf

BARK_KEY = os.environ.get("BARK_KEY")
SECTOR_ANCHOR = "SOXX"
LONG_TERM_STOCKS = ["VOO", "QQQ", "GOOG", "NVDA", "MU"]

ROE_THRESHOLD = 0.15              
PE_MAX_THRESHOLD = 35             
RSI_BUY_LINE = 35                 

def send_to_bark(title: str, content: str, group: str = "长线价值抄底"):
    if not BARK_KEY:
        print(f"\n⚠️ 网页端实时诊断输出 -> \n【{title}】\n{content}\n")
        return
    encoded_title = urllib.parse.quote_plus(title)
    encoded_content = urllib.parse.quote_plus(content)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_content}?group={encoded_group}&sound=calypso"
    try: requests.get(url, timeout=10)
    except Exception as e: print(f"❌ 推送失败: {e}")

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    deltas = prices.diff().dropna()
    gains = deltas.clip(lower=0)
    losses = -deltas.clip(upper=0)
    avg_gain = gains.ewm(com=period-1, min_periods=period).mean()
    avg_loss = losses.ewm(com=period-1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return (100 - (100 / (1 + rs))).iloc[-1]

def diagnose_sector_background():
    print(f"🩺 正在拉取半导体全行业核心指数 [{SECTOR_ANCHOR}] 进行现场诊断...")
    try:
        sector = yf.Ticker(SECTOR_ANCHOR)
        hist = sector.history(period="250d")
        current_price = hist['Close'].iloc[-1]
        ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        sector_rsi = calculate_rsi(hist['Close'])
        return sector_rsi, current_price > ma200
    except Exception as e:
        print(f"❌ 行业背景诊断失败: {e}")
        return 50, True

def execute_combined_diagnosis():
    print("🚀 启动 [半导体大背景 + 个股基本面联合对冲诊断系统]...")
    sector_rsi, sector_is_bull = diagnose_sector_background()
    
    for ticker_symbol in LONG_TERM_STOCKS:
        try:
            print(f"🔍 正在交叉诊断标的基本面: {ticker_symbol} ...")
            ticker = yf.Ticker(ticker_symbol)
            info = ticker.info
            
            if ticker_symbol not in ["VOO", "QQQ"]:
                roe = info.get("returnOnEquity", 0)
                pe = info.get("trailingPE", 0)
                if roe is None or roe < ROE_THRESHOLD: continue
                if pe is None or pe > PE_MAX_THRESHOLD or pe == 0: continue

            hist = ticker.history(period="250d")
            if len(hist) < 210: continue
            current_price = hist['Close'].iloc[-1]
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            current_rsi = calculate_rsi(hist['Close'])
            is_stock_above_ma200 = current_price > ma200
            
            if not is_stock_above_ma200 and sector_rsi <= 38:
                push_title = f"⚠️ 行业踩踏警报：【{ticker_symbol}】中线趋势破位"
                push_content = f"🛰️ 行业RSI为 {sector_rsi:.1f}，处于抛售期。\n❌ {ticker_symbol} 股价 ${current_price:.2f} 已跌破200日生命线 (${ma200:.2f})。\n💡 建议: 个股伤势过重，【拒绝右侧接飞刀】，锁死仓位！"
                send_to_bark(title=push_title, content=push_content, group="半导体联合诊断")

            elif is_stock_above_ma200 and (current_rsi <= RSI_BUY_LINE or sector_rsi <= 35):
                push_title = f"💎 黄金坑确立：【{ticker_symbol}】行业泥石流中的强韧真金！"
                push_content = f"浪 行业背景: 半导体大盘已跌透 (RSI: {sector_rsi:.1f})。\n🛡️ 个股强韧: 死守200日线线上方，实时RSI: {current_rsi:.1f}。\n⚡ 建议: 经典的【高质量回调建仓点】，2w美元资产中的机动资金可分批介入！"
                send_to_bark(title=push_title, content=push_content, group="半导体联合诊断")
            time.sleep(1)
        except Exception as e: continue

if __name__ == "__main__":
    # 强制在主入口也增加一行手机连通性验证
    send_to_bark("✨ 系统重启通知", "您的 GitHub 2026 美股双策略量化系统已从零重建成功！测试链路完全畅通。", "系统管理")
    execute_combined_diagnosis()
