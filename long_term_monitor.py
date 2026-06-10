import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import yfinance as yf

# ==========================================
# 1. 配置参数与自动股票池获取
# ==========================================
MAX_WORKERS = 12      # 并发线程数（10-15最佳，过高易被雅虎限流）
MAX_RETRIES = 3       # 下载失败后的最大重试次数
BACK_DAYS = 365       # 获取历史数据的天数（确保满足200天均线计算）

def get_sp500_tickers():
    """
    从维基百科自动实时抓取最新的标普 500 成分股列表。
    如果抓取失败，则启用标准蓝筹股作为兜底。
    """
    try:
        url = "https://wikipedia.org"
        tables = pd.read_html(url)
        df = tables[0]
        # 替换雅虎财经中特殊的符号点，例如 BRK.B 替换为 BRK-B
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        return tickers
    except Exception as e:
        print(f"⚠️ 无法实时获取标普500列表 ({e})，正在启用核心蓝筹股作为兜底...")
        return [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", 
            "V", "JPM", "UNH", "JNJ", "WMT", "PG", "XOM", "AMD", "COST"
        ]

# ==========================================
# 2. 核心量化指标计算
# ==========================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    输入单只股票的历史 DataFrame，计算技术指标。
    必须使用 'Adj Close' (后复权价) 避免因分红拆股导致指标失真。
    """
    if df.empty or len(df) < 200:
        return df
        
    # 计算 200日简单移动平均线 (SMA 200)
    df['SMA_200'] = df['Adj Close'].rolling(window=200).mean()
    
    # 计算 14日相对强弱指标 (RSI 14)
    delta = df['Adj Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)  # 防止除以0
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    return df

# ==========================================
# 3. 容错与并发数据获取
# ==========================================
def fetch_stock_data(ticker: str) -> dict:
    """
    单只股票的数据拉取函数。包含重试机制、技术面计算与基本面多因子过滤。
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 1. 初始化 Ticker 并获取基本面财务数据
            ticker_obj = yf.Ticker(ticker)
            info = ticker_obj.info
            
            # 提取基本面因子（加入默认值兜底，防止无数据报错）
            pe_ratio = info.get('trailingPE', None)
            profit_margin = info.get('profitMargins', None)
            current_price = info.get('currentPrice', None)
            
            # 2. 下载历史 K 线数据 (自动使用后复权)
            df_history = ticker_obj.history(period=f"{BACK_DAYS}d")
            
            if df_history.empty or len(df_history) < 200:
                return {"ticker": ticker, "status": "error", "reason": "历史数据不足200天"}
            
            # 3. 向量化计算指标
            df_history = calculate_indicators(df_history)
            latest_row = df_history.iloc[-1]
            
            # 提取最新一天的计算结果
            price = current_price if current_price else latest_row['Adj Close']
            sma_200 = latest_row['SMA_200']
            rsi_14 = latest_row['RSI_14']
            
            return {
                "ticker": ticker,
                "status": "success",
                "price": round(price, 2) if price else None,
                "sma_200": round(sma_200, 2) if not pd.isna(sma_200) else None,
                "rsi_14": round(rsi_14, 2) if not pd.isna(rsi_14) else None,
                "pe_ratio": round(pe_ratio, 2) if pe_ratio else None,
                "profit_margin": round(profit_margin * 100, 2) if profit_margin else None
            }
            
        except Exception as e:
            if attempt == MAX_RETRIES:
                return {"ticker": ticker, "status": "error", "reason": f"重试{MAX_RETRIES}次后仍失败: {str(e)}"}
            time.sleep(1.5 * attempt) # 指数级退避延迟，降低被雅虎拒绝的概率

# ==========================================
# 4. 主执行流程与策略筛选
# ==========================================
def main():
    # 动态获取股票池
    tickers = get_sp500_tickers()
    print(f"🚀 开始多线程增效监控，当前股票池总数: {len(tickers)} 只...")
    start_time = time.time()
    
    results = []
    # 使用线程池加速网络 I/O 密集型任务
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_ticker = {executor.submit(fetch_stock_data, t): t for t in tickers}
        for future in as_completed(future_to_ticker):
            res = future.result()
            if res and res.get("status") == "success":
                results.append(res)
                
    if not results:
        print("❌ 未成功获取到任何股票数据，脚本退出。")
        return
        
    df_all = pd.DataFrame(results)
    
    # ------------------------------------------
    # 5. 长线量化多因子筛选条件
    # ------------------------------------------
    # 确保价格、均线和 RSI 数据有效
    df_all = df_all.dropna(subset=['price', 'sma_200', 'rsi_14'])
    
    # 条件1 (技术面): 价格站上200日均线（多头趋势）
    cond_trend = df_all['price'] > df_all['sma_200']
    # 条件2 (技术面): RSI < 60（非严重超买状态，留有上涨空间）
    cond_rsi = df_all['rsi_14'] < 60
    # 条件3 (基本面): 存在市盈率且 0 < PE < 35（剔除无利润亏损股以及高泡沫股）
    cond_pe = (df_all['pe_ratio'].notna()) & (df_all['pe_ratio'] > 0) & (df_all['pe_ratio'] < 35)
    # 条件4 (基本面): 净利润率 > 10%（具备较强的行业赚钱护城河）
    cond_margin = (df_all['profit_margin'].notna()) & (df_all['profit_margin'] > 10)
    
    # 综合过滤
    df_filtered = df_all[cond_trend & cond_rsi & cond_pe & cond_margin]
    
    # 按市盈率低到高排序，优先展示低估值优质资产
    df_filtered = df_filtered.sort_values(by="pe_ratio", ascending=True)
    
    # ------------------------------------------
    # 6. 生成漂亮的 Markdown 报告
    # ------------------------------------------
    duration = round(time.time() - start_time, 2)
    
    markdown_output = f"""# 📈 美股长线策略每日监控报告
- **扫描范围**: 标普 500 成分股 (S&P 500)
- **执行耗时**: {duration} 秒
- **成功请求数**: {len(df_all)} 只
- **触发多头且估值合理股票数**: {len(df_filtered)} 只

### 🎯 筛选通过列表 (多头趋势 + 低估值 + 强盈利)
"""
    if df_filtered.empty:
        markdown_output += "\n> 💨 今日暂无股票满足复合筛选条件。\n"
    else:
        # 美化表格列名
        report_table = df_filtered.rename(columns={
            "ticker": "代码", "price": "现价 ($)", "sma_200": "200日均线", 
            "rsi_14": "RSI(14)", "pe_ratio": "市盈率(PE)", "profit_margin": "净利润率 (%)"
        })
        markdown_output += report_table[[
            "代码", "现价 ($)", "200日均线", "RSI(14)", "市盈率(PE)", "净利润率 (%)"
        ]].to_markdown(index=False)
        
    # 同时输出到控制台与本地文件
    print("\n" + markdown_output)
    with open("stock_monitor_report.md", "w", encoding="utf-8") as f:
        f.write(markdown_output)
    print("💾 报告已成功保存至本地本地文件: stock_monitor_report.md")

if __name__ == "__main__":
    main()
