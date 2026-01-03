import yfinance as yf
import requests
import pandas as pd
import pandas_ta_classic as ta
import time
import os

# --- 配置区：从 GitHub Secrets 读取 ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 监控名单
WATCHLIST = {
    "5347.KL": {"name": "TENAGA", "target_pe": 16, "min_div": 3.5},
    "0166.KL": {"name": "INARI", "target_pe": 28, "min_div": 3.0},
    "0097.KL": {"name": "VITROX", "target_pe": 40, "min_div": 1.5},
    "0022.KL": {"name": "GRENTEC", "target_pe": 32, "min_div": 1.0},
    "0128.KL": {"name": "FRONTKN", "target_pe": 28, "min_div": 1.2},
    "ECOWLD.KL": {"name": "ECOWLD", "target_pe": 15, "min_div": 4.5},
    "UEMS.KL": {"name": "UEMS", "target_pe": 25, "min_div": 0.0}
}

def send_telegram_msg(message):
    if not TOKEN or not CHAT_ID:
        print("错误: TOKEN 或 CHAT_ID 未设置")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    try:
        requests.get(url, timeout=15)
    except Exception as e:
        print(f"发送 Telegram 失败: {e}")

def get_rsi(symbol):
    try:
        df = yf.download(symbol, period="2mo", interval="1d", progress=False)
        if df.empty or len(df) < 15: 
            return None
        rsi_series = ta.rsi(df["Close"], length=14)
        if rsi_series is None or rsi_series.empty:
            return None
        return float(rsi_series.iloc[-1])
    except Exception as e:
        print(f"无法计算 {symbol} 的 RSI: {e}")
        return None

def check_stocks():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始扫描...")
    has_alert = False
    
    for symbol, criteria in WATCHLIST.items():
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            if not info or 'currentPrice' not in info:
                print(f"⚠️ 跳过 {symbol}: 无效数据")
                continue
            
            current_price = info.get("currentPrice")
            pe_ratio = info.get("trailingPE")
            
            # --- 股息率计算修正逻辑 ---
            div_rate = info.get("dividendRate")
            if div_rate and current_price:
                # 方式A：使用 每股派息额 / 股价 (最准)
                div_yield = (div_rate / current_price) * 100
            else:
                # 方式B：备用方案
                raw_yield = info.get("dividendYield", 0)
                div_yield = (raw_yield * 100) if raw_yield else 0
                
            # 如果算出来还是超过 100%，通常是因为数据已经是百分比格式了，进行归一化
            if div_yield > 100:
                div_yield = div_yield / 100

            rsi_val = get_rsi(symbol)
            
            # 建立提醒条件
            triggers = []
            if pe_ratio and pe_ratio <= criteria["target_pe"]:
                triggers.append(f"✅ PE低估: {pe_ratio:.2f}")
            if div_yield >= criteria["min_div"] and criteria["min_div"] > 0:
                triggers.append(f"💰 高股息: {div_yield:.2f}%")
            if rsi_val is not None and rsi_val <= 30:
                triggers.append(f"📉 RSI超卖: {rsi_val:.2f}")

            if triggers:
                has_alert = True
                # 彻底避开 f-string 内部的反斜杠错误
                header = "🌟【马股预警】" + criteria['name'] + " (" + symbol + ")\n"
                price_line = "股价: RM " + str(current_price) + "\n"
                separator = "-------------------\n"
                body = ""
                for t in triggers:
                    body += t + "\n"
                footer = "-------------------\n请核实基本面后决策。"
                
                full_msg = header + price_line + separator + body + footer
                send_telegram_msg(full_msg)
                print(f"提醒已发送: {criteria['name']}")

        except Exception as e:
            print(f"❌ 处理 {symbol} 时出错: {e}")
            continue

    if not has_alert:
        print("今日无符合买入条件的股票。")

if __name__ == "__main__":
    check_stocks()
