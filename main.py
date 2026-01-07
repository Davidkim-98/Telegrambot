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

# 屏蔽 yfinance 产生的 HTTP 404/日志噪音
logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- 环境配置 ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HISTORY_FILE = "history.json"
SUMMARY_FILE = "summary.json"

# --- 严格监控参数 (基于高股息+低估值策略) ---
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
            with open(file_path, 'r') as f: return json.load(f)
        except: return []
    return []

def save_json(file_path, data):
    with open(file_path, 'w') as f: json.dump(data, f)

def send_telegram_msg(message):
    if not TOKEN or not CHAT_ID: return None
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    try:
        res = requests.get(url, timeout=15).json()
        if res.get("ok"): return res["result"]["message_id"]
    except Exception as e:
        print(f"发送失败: {e}")
    return None

def clean_old_messages(history):
    now = datetime.now()
    remaining = []
    print("正在清理过期消息记录...")
    for entry in history:
        sent_time = datetime.fromisoformat(entry['time'])
        # 超过7天的消息尝试从TG撤回
        if now - sent_time > timedelta(days=7):
            url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage?chat_id={CHAT_ID}&message_id={entry['msg_id']}"
            try: requests.get(url, timeout=10)
            except: pass
        else:
            remaining.append(entry)
    return remaining

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
    print(f"[{today_str}] 马股自动化监控启动...")
    
    history = load_json(HISTORY_FILE)
    history = clean_old_messages(history)
    weekly_summary = load_json(SUMMARY_FILE)
    
    has_any_trigger = False
    
    for symbol, criteria in WATCHLIST.items():
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            if not info or 'currentPrice' not in info: continue
            
            price = info.get("currentPrice")
            pe = info.get("trailingPE")
            
            # 股息率修正逻辑 (优先使用 Rate / Price)
            div_rate = info.get("dividendRate")
            div_yield = (div_rate / price * 100) if div_rate else (info.get("dividendYield", 0) * 100)
            if div_yield > 100: div_yield /= 100

            rsi_val = get_rsi(symbol)
            
            triggers = []
            if pe and pe <= criteria["target_pe"]:
                triggers.append(f"✅ PE低估({pe:.2f})")
            if div_yield >= criteria["min_div"] and criteria["min_div"] > 0:
                triggers.append(f"💰 高股息({div_yield:.2f}%)")
            if rsi_val and rsi_val <= 30:
                triggers.append(f"📉 RSI超卖({rsi_val:.2f})")

            if triggers:
                has_any_trigger = True
                header = f"📅 [{today_str}] 触发买入信号\n公司: {criteria['name']} ({symbol})\n"
                msg_body = f"股价: RM {price}\n-------------------\n" + "\n".join(triggers) + "\n-------------------\n此消息7天后自动撤回。"
                
                msg_id = send_telegram_msg(header + msg_body)
                if msg_id:
                    history.append({"msg_id": msg_id, "time": datetime.now().isoformat()})
                
                weekly_summary.append({
                    "date": today_str, "name": criteria['name'], "price": price, "reason": " & ".join(triggers)
                })
        except Exception as e:
            print(f"处理 {symbol} 错误: {e}")
            continue

    # 保存消息ID历史
    save_json(HISTORY_FILE, history)
    
    # 如果今天没有任何触发，发一个“平安信”确认程序在运行
    if not has_any_trigger:
        send_telegram_msg(f"📅 [{today_str}] 扫描完成。当前市场暂未触发【严格买入】条件，继续空仓观望。")

    # 周五周报汇总
    if today.weekday() == 4:
        if weekly_summary:
            report = f"📊 【本周机会总结】 {today_str}\n-------------------\n"
            for item in weekly_summary:
                report += f"• {item['date']}: {item['name']} (RM {item['price']})\n  信号: {item['reason']}\n\n"
            report += "-------------------\n祝周末愉快！"
            send_telegram_msg(report)
            weekly_summary = []
        else:
            send_telegram_msg(f"📊 [{today_str}] 本周扫描结束，无符合条件的捡漏机会。")
    
    save_json(SUMMARY_FILE, weekly_summary)
    print("扫描流程结束。")

if __name__ == "__main__":
    check_stocks()
    sys.exit(0)
