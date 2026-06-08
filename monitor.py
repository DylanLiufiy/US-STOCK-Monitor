import os
import sys
import json
from datetime import datetime, timedelta
import requests
import polars as pl
import yfinance as yf

# ==============================================================================
# ❄️ 56只全行业立体对冲【Trade25 专属免佣风控】系统 (V5 终极实盘体)
# ==============================================================================

BARK_KEY = "请在这里替换成你的Bark_Key"
LEDGER_FILE = "portfolio_ledger_v5.json"
INITIAL_BUDGET = 30000.0   
MAX_DRAWDOWN_LIMIT = 5.0   

# 🔑 Trade25 政策精细参数配置
TRADE25_MONTHLY_FREE_LIMIT_HKD = 250000.0   # 每月 25 万港币免佣金上限
USD_TO_HKD_FX_RATE = 7.8                    # 美元兑港币计价固定汇率
POST_FREE_MIN_COMMISSION_USD = 1.99         # 额度用完后，单笔买卖最低惩罚性佣金

STRATEGY_PORTFOLIO_CONFIG = {
    "CORE_STABLE": {"name": "安全底座层", "single_invest_usd": 1500.0, "tickers": ["SPY", "QQQ", "NVDA", "AVGO", "MSFT", "LLY", "NVO", "WM", "KO"]},
    "AGGRESSIVE_GROWTH": {"name": "略微激进层", "single_invest_usd": 1000.0, "tickers": ["GE", "EMR", "ROK", "HON", "RTX", "LMT", "CEG", "VST", "NEE", "COIN", "HOOD", "PYPL"]},
    "DARK_HORSE": {"name": "强黑马层", "single_black_horse_cap": 450.0, "tickers": ["PLTR", "PATH", "BBAI", "SOUN", "EH", "JOBY", "ACHR", "RKLB", "IONQ", "RGTI", "CRSP", "NTLA", "DNA", "ARWR"]}
}

HEDGE_INSTRUMENT = "SQQQ"   
ALL_TICKERS = [t for layer in STRATEGY_PORTFOLIO_CONFIG.values() for t in layer["tickers"]] + [HEDGE_INSTRUMENT, "SPY"]
ALL_TICKERS = list(set(ALL_TICKERS))


def load_ledger_v5():
    """初始化V5账本，新增记录Trade25月度额度消耗和上一次重置月份"""
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, 'r', encoding='utf-8') as f:
            ledger = json.load(f)
            # 自动跨月重置机制：如果进入了新的一月，自动将已用免费额度清零重置
            current_month = datetime.now().strftime("%Y-%m")
            if ledger.get("last_reset_month", "") != current_month:
                ledger["trade25_used_hkd"] = 0.0
                ledger["last_reset_month"] = current_month
                print(f"📅 检测到进入新月份 {current_month}，系统已自动重置 Trade25 25万港币免佣额度！")
            return ledger
            
    return {
        "cash": INITIAL_BUDGET, 
        "holdings": {}, 
        "history_trades": [], 
        "daily_net_worth_history": [], 
        "spy_benchmark_shares": None,
        "circuit_breaker_active": False, 
        "spy_above_sma20_days": 0, 
        "pushed_news_ids": [],
        "trade25_used_hkd": 0.0,                    # 📊 本月已经消耗掉的港币免佣交易额
        "last_reset_month": datetime.now().strftime("%Y-%m")
    }

def save_ledger_v5(ledger):
    with open(LEDGER_FILE, 'w', encoding='utf-8') as f: json.dump(ledger, f, indent=4, ensure_ascii=False)


def execute_order_and_log_v5(ticker, action_type, price, amount_usd, ledger):
    """
    【核心重构优化点】：严格核算每笔交易带来的 Trade25 港币额度损耗。
    一旦下周一开启运行，只要额度没有超过 25 万，单笔执行手续费死死卡为 0 元。
    """
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. 基础熔断拦截
    if action_type == "BUY" and ledger.get("circuit_breaker_active", False):
        print(f"🔒 熔断锁拦截：当前系统处于防御期，谢绝买入 {ticker}。")
        return False

    # 2. 计算此笔交易需要消耗的港币额度 (交易本金转换)
    trade_value_hkd = amount_usd * USD_TO_HKD_FX_RATE
    
    # 3. 判定此笔买卖是否仍处在 Trade25 的 25万免佣金金牌护身符下
    is_free_trade = (ledger["trade25_used_hkd"] + trade_value_hkd) <= TRADE25_MONTHLY_FREE_LIMIT_HKD
    
    # 计算本笔交易的手续费摩擦成本
    commission_cost_usd = 0.0 if is_free_trade else POST_FREE_MIN_COMMISSION_USD
    
    if action_type == "BUY":
        # 扣除购买本金 + 可能存在的惩罚性佣金
        total_buy_cost = amount_usd + commission_cost_usd
        if ledger["cash"] < total_buy_cost:
            print(f"❌ 现金池余额不足以支付 {ticker} 本金加佣金共 ${total_buy_cost:.2f}，拦截交易。")
            return False
            
        shares_to_buy = round(amount_usd / price, 4)
        ledger["cash"] -= total_buy_cost
        
        # 更新持仓
        if ticker in ledger["holdings"]:
            old_s = ledger["holdings"][ticker]["shares"]
            old_c = ledger["holdings"][ticker]["entry_price"]
            new_s = old_s + shares_to_buy
            new_c = ((old_s * old_c) + total_buy_cost) / new_s # 手续费平摊入持仓成本中
            ledger["holdings"][ticker] = {"shares": round(new_s, 4), "entry_price": round(new_c, 2)}
        else:
            ledger["holdings"][ticker] = {"shares": shares_to_buy, "entry_price": round(total_buy_cost / shares_to_buy, 2)}
            
        # 实时扣减累加本月已消耗的 Trade25 免费港币额度
        ledger["trade25_used_hkd"] += trade_value_hkd
        
        ledger["history_trades"].append({
            "date": now_str, "ticker": ticker, "type": "BUY", "shares": shares_to_buy, "price": price, 
            "commission_paid_usd": commission_cost_usd, "hkd_quota_consumed": round(trade_value_hkd, 2)
        })
        print(f"🛒 成功建仓 {ticker}：本笔消耗免费额度 {trade_value_hkd:.1f} HKD，实际支付手续费: ${commission_cost_usd}")
        return True
        
    elif action_type == "SELL" and ticker in ledger["holdings"]:
        holding_info = ledger["holdings"].pop(ticker)
        gross_return_cash = holding_info["shares"] * price
        
        # 卖出回笼资金时也要扣除可能存在的佣金
        net_returned_cash = gross_return_cash - commission_cost_usd
        ledger["cash"] += net_returned_cash
        
        ledger["trade25_used_hkd"] += (gross_return_cash * USD_TO_HKD_FX_RATE)
        pnl = net_returned_cash - (holding_info["entry_price"] * holding_info["shares"])
        
        ledger["history_trades"].append({
            "date": now_str, "ticker": ticker, "type": "SELL", "shares": holding_info["shares"], "price": price,
            "commission_paid_usd": commission_cost_usd, "pnl": round(pnl, 2)
        })
        print(f"💰 成功平仓 {ticker}：实际到账金额: ${net_returned_cash:.2f}，手续费: ${commission_cost_usd}")
        return True
        
    return False


def run_survivor_v5_pipeline():
    """主控运行：盘点营收并生成带有 Trade25 额度监控的早报发往 Bark"""
    ledger = load_ledger_v5()
    now_str = datetime.now().strftime('%Y-%m-%d')
    
    try:
        market_data = yf.download(ALL_TICKERS, period="60d", group_by='ticker', threads=True, progress=False)
    except Exception as e:
        print(f"拉取失败: {e}")
        return

    # 1. 计算总市值
    current_stock_value = 0.0
    for ticker, info in ledger["holdings"].items():
        try: current_stock_value += info["shares"] * float(market_data.get(ticker)['Close'].iloc[-1])
        except: current_stock_value += info["shares"] * info["entry_price"]
        
    total_net_worth = ledger["cash"] + current_stock_value
    
    # 2. 统计 Trade25 的可用额度剩余
    remaining_free_hkd = max(0.0, TRADE25_MONTHLY_FREE_LIMIT_HKD - ledger["trade25_used_hkd"])
    free_quota_pct = (remaining_free_hkd / TRADE25_MONTHLY_FREE_LIMIT_HKD) * 100
    
    # 3. 组装资产报告文本
    report_title = "🛡️ 寿星 V5 策略盘点 (Trade25 额度护航)"
    report_body = f"### 📊 账户生存与 Trade25 额度盘点 ({now_str})\n\n"
    report_body += f"* **目前总资产净值 (NAV)**: `${total_net_worth:,.2f}`\n"
    report_body += f"* **可用风控流动现金池**: `${ledger['cash']:,.2f}`\n"
    report_body += f"  └── *当前持仓标的汇总*: `{list(ledger['holdings'].keys()) if ledger['holdings'] else '全部安全空仓'}`\n\n"
    
    report_body += "#### 🎫 Trade25 免佣额度追踪看板\n"
    report_body += f"* **本月已用免佣金交易量**: `{ledger['trade25_used_hkd']:,.2f} HKD`\n"
    report_body += f"* **剩余完全免佣港币额度**: `{remaining_free_hkd:,.2f} HKD` (占比: `{free_quota_pct:.1f}%`)\n"
    
    if remaining_free_hkd > 0:
        report_body += "  └── 🎉 *状态：下周一买卖将保持【100%完全免佣金】丝滑模式运行！*\n"
    else:
        report_body += f"  └── ⚠️ *警告：本月免佣金额度已耗尽！后续单笔买卖将每笔严格计入 ${POST_FREE_MIN_COMMISSION_USD} 最低手续费摩擦！*\n"
        
    report_body += f"\n*💡 提示：跨月系统会自动清零并重新赋予 25 万 HKD 额度。数据已安全持久化写入本地盘。*"

    save_ledger_v4(ledger) # 保存账本状态
    
    if BARK_KEY != "请在这里替换成你的Bark_Key":
        requests.post(f"https://day.app{BARK_KEY}", data={"title": report_title, "body": report_body, "group": "Trade25量化流", "isArchive": 1}, timeout=10)
    print(report_body)


if __name__ == "__main__":
    run_survivor_v5_pipeline()
