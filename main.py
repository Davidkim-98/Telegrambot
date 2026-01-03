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
SUMMARY_FILE = "summary.json" # 新增：周报记录文件

WATCHLIST = {
    "5347.KL": {"name": "TENAGA", "target_pe": 14, "min_div": 4.5},  # 5年均值以上
    "0166.KL": {"name": "INARI", "target_pe": 22, "min_div": 3.8},   # 捕捉深度回调
    "0097.KL": {"name": "VITROX", "target_pe": 35, "min_div": 1.0},  # 极罕见的1%收益率
    "0022.KL": {"name": "GRENTEC", "target_pe": 28, "min_div": 1.8}, # 自动化板块低点
    "0128.KL": {"name": "FRONTKN", "target_pe": 25, "min_div": 1.5}, # 5年高股息点
    "ECOWLD.KL": {"name": "ECOWLD", "target_pe": 12, "min_div": 5.5},# 房产股的高息吸引力
    "UEMS.KL": {"name": "UEMS", "target_pe": 18, "min_div": 3.0}     # 捕捉估值修复前夕
}

def load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f)

def clean_old_messages(history):
    now = datetime.now()
    remaining = []
    print("正在检查并清理 7 天前的旧消息...")
    for entry in history:
        sent_time = datetime.fromisoformat(entry['time'])
        if now - sent_time > timedelta(days=7):
            url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage?chat_id={CHAT_ID}&message_id={entry['msg_id']}"
            try: requests.get(url, timeout=10)
            except: pass
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
    except: pass
    return None

def get_rsi(symbol):
    try:
        df = yf.download(symbol, period="2mo", interval="1d", progress=False, threads=False)
        if df.empty or len(df) < 15: return None
        rsi_series = ta.rsi(df["Close"], length=14)
        return float(rsi_series.iloc[-1]) if rsi_series is not None else None
    except: return None

def check_stocks():
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    print(f"[{today_str}] 开始扫描马股...")
    
    history = load_json(HISTORY_FILE)
    history = clean_old_messages(history)
    weekly_summary = load_json(SUMMARY_FILE)
    
    has_daily_alert = False
    
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
                triggers.append(f"PE低估({pe_ratio:.2f})")
            if div_yield >= criteria["min_div"] and criteria["min_div"] > 0:
                triggers.append(f"高股息({div_yield:.2f}%)")
            if rsi_val and rsi_val <= 30:
                triggers.append(f"RSI超卖({rsi_val:.2f})")

            if triggers:
                has_daily_alert = True
                trigger_str = ", ".join(triggers)
                
                # 发送即时提醒
                header = "📅 [" + today_str + "] 马股预警\n"
                header += "公司: " + criteria['name'] + " (" + symbol + ")\n"
                price_line = "股价: RM " + str(current_price) + "\n"
                body = "-------------------\n触发: " + trigger_str + "\n-------------------\n此消息7天后自动删除。"
                
                msg_id = send_telegram_msg(header + price_line + body)
                if msg_id:
                    history.append({"msg_id": msg_id, "time": datetime.now().isoformat()})
                
                # 记录到周报缓存
                weekly_summary.append({
                    "date": today_str,
                    "name": criteria['name'],
                    "symbol": symbol,
                    "reason": trigger_str,
                    "price": current_price
                })

        except: continue

    # 保存消息历史
    save_json(HISTORY_FILE, history)
    
    # 如果是周五 (weekday 为 4)，发送周报汇总
    if today.weekday() == 4:
        print("今日周五，正在生成周报汇总...")
        if weekly_summary:
            report_header = "📊 【本周预警汇总】 📊\n时间: " + today_str + "\n-------------------\n"
            report_body = ""
            # 去重：如果同一只股票一周触发多次，按日期列出
            for item in weekly_summary:
                report_body += "- " + item['date'] + ": " + item['name'] + " (RM " + str(item['price']) + ")\n  原因: " + item['reason'] + "\n\n"
            
            report_footer = "-------------------\n祝您周末愉快！本周记录已清空。"
            send_telegram_msg(report_header + report_body + report_footer)
            # 清空周报缓存
            weekly_summary = []
        else:
            send_telegram_msg("📊 本周扫描结束，无股票触发预警。祝您周末愉快！")
    
    save_json(SUMMARY_FILE, weekly_summary)
    print("扫描流程结束。")

if __name__ == "__main__":
    check_stocks()
    sys.exit(0)
