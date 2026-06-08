import os
import time
import urllib.parse
import xml.etree.ElementTree as ET
import requests
import yfinance as yf

BARK_KEY = os.environ.get("BARK_KEY")
MONITOR_STOCKS = ["GOOG", "NVDA", "MU"] 
MACRO_KEYWORDS = ["Fed interest rate", "US CPI", "Inflation"]

def send_to_bark(title: str, body: str, group: str = "股市监控"):
    if not BARK_KEY:
        print("❌ 错误：未在 GitHub Secrets 中配置 BARK_KEY 环境变量！")
        return
    encoded_title = urllib.parse.quote_plus(title)
    encoded_body = urllib.parse.quote_plus(body)
    encoded_group = urllib.parse.quote_plus(group)
    url = f"https://day.app{BARK_KEY}/{encoded_title}/{encoded_body}?group={encoded_group}&sound=bell"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print(f"🔔 成功推送通知：【{title}】")
        else:
            print(f"❌ Bark 推送失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"❌ 推送网络异常: {e}")

def get_macro_news_from_google():
    print("⏳ 正在扫描 Google News 宏观经济新闻...")
    query = " OR ".join([f'"{kw}"' for kw in MACRO_KEYWORDS])
    rss_url = f"https://google.com{urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(rss_url, headers=headers, timeout=10)
        root = ET.fromstring(res.text)
        for item in root.findall(".//item")[:1]:
            title = item.find("title").text
            link = item.find("link").text
            push_content = f"链接: {link}"
            send_to_bark(title="🏛️ 宏观政策预警", body=push_content, group="宏观大盘")
    except Exception as e:
        print(f"❌ 抓取谷歌宏观新闻失败: {e}")

def get_stock_news_from_yfinance():
    print("⏳ 正在扫描监控个股的核心财报与供应链新闻...")
    for ticker_symbol in MONITOR_STOCKS:
        try:
            ticker = yf.Ticker(ticker_symbol)
            news_list = ticker.news
            if not news_list: continue
            latest_news = news_list[0]
            title = latest_news.get("title")
            link = latest_news.get("link")
            push_title = f"📊 监控股 {ticker_symbol} 新闻"
            push_content = f"标题: {title}\n链接: {link}"
            send_to_bark(title=push_title, body=push_content, group="个股财报")
            time.sleep(1)
        except Exception as e:
            print(f"❌ 抓取个股 {ticker_symbol} 新闻失败: {e}")

def main():
    print("🚀 独立美股新闻量化监控系统已启动...")
    get_macro_news_from_google()
    get_stock_news_from_yfinance()
    print("🏁 今日新闻扫描并推送完成。")

if __name__ == "__main__":
    main()
