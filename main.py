import yfinance as yf
import requests
import pandas as pd
import pandas_ta_classic as ta
import time
import os
import sys
import logging
import json
from datetime import datetime, timedelta

# 屏蔽日志
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# 配置
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HISTORY_FILE = "history.json"

WATCHLIST = {
    "5347.KL": {"name": "TENAGA", "target_pe": 16, "min_div": 3.5},
    "0166.KL": {"name": "INARI", "target_pe": 28, "min_div": 3.0},
    "0097.KL": {"name": "VITROX", "target_pe": 40, "min_div": 1.5},
    "0022.KL": {"name": "GRENTEC", "target_pe": 32, "min_div": 1.0},
    "0128.KL": {"name": "FRONTKN", "target_pe": 28, "min_div": 1.2},
    "ECOWLD.KL": {"name": "ECOWLD", "target_pe": 15, "min_div": 4.5},
    "UEMS.KL": {"name": "UEMS", "target_pe": 25, "min_div": 0.0}
}

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def clean_old_messages(history):
    """删除 7 天前的消息"""
    now = datetime.now()
    remaining = []
    print("正在检查并清理 7 天前的旧消息...")
    
    for entry in history:
        sent_time = datetime.fromisoformat(entry['time'])
        if now - sent_time > timedelta(days=7):
            # 调用删除 API
            url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage?chat_id={CHAT_ID}&message_id={entry['msg_id']}"
            try:
                requests.get(url, timeout=10)
            except:
                pass
        else:
            remaining.append(entry)
    return remaining

def send_telegram_msg(message):
    if not TOKEN or not CHAT_ID: return None
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    try:
        res = requests.get(url, timeout=15).json()
        if res.get("ok"):
            return res["result"]["message_id"]
    except:
        pass
    return None

def get_rsi(symbol):
    try:
        df = yf.download(symbol, period="2mo", interval="1d", progress=False, threads=False)
        if df.empty or len(df) < 15: return None
        rsi_series = ta.rsi(df["Close"], length=14)
        return float(rsi_series.iloc[-1]) if rsi_series is not None else None
    except: return None

def check_stocks():
    # 获取当前日期（大马时间）
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"[{today_str}] 开始扫描马股...")
    
    history = load_history()
    history = clean_old_messages(history)
    
    has_alert = False
    for symbol, criteria in WATCHLIST.items():
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            if not info or 'currentPrice' not in info: continue
            
            current_price = info.get("currentPrice")
            pe_ratio = info.get("trailingPE")
            
            div_rate = info.get("dividendRate")
            div_yield = (div_rate / current_price * 100) if div_rate else (info.get("dividendYield", 0) * 100)
            if div_yield > 100: div_yield /= 100

            rsi_val = get_rsi(symbol)
            
            triggers = []
            if pe_ratio and pe_ratio <= criteria["target_pe"]:
                triggers.append(f"✅ PE低估: {pe_ratio:.2f}")
            if div_yield >= criteria["min_div"] and criteria["min_div"] > 0:
                triggers.append(f"💰 高股息: {div_yield:.2f}%")
            if rsi_val and rsi_val <= 30:
                triggers.append(f"📉 RSI超卖: {rsi_val:.2f}")

            if triggers:
                has_alert = True
                # 在标题加入日期
                header = f"📅 [{today_str}] 马股预警\n"
                header += f"公司: {criteria['name']} ({symbol})\n"
                price_line = f"股价: RM {current_price}\n"
                body = "-------------------\n" + "\n".join(triggers) + "\n-------------------\n请核实。此消息7天后自动删除。"
                
                msg_id = send_telegram_msg(header + price_line + body)
                if msg_id:
                    history.append({"msg_id": msg_id, "time": datetime.now().isoformat()})

        except: continue

    save_history(history)
    print("扫描流程结束。")

if __name__ == "__main__":
    check_stocks()
    sys.exit(0)
