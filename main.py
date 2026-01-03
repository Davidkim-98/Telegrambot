import yfinance as yf
import requests
import pandas as pd
import pandas_ta_classic as ta
import time
import os  # 必须导入

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
    "8123.KL": {"name": "ECOWLD", "target_pe": 15, "min_div": 4.5},
    "5148.KL": {"name": "UEMS", "target_pe": 25, "min_div": 0.0}
}

def send_telegram_msg(message):
    if not TOKEN or not CHAT_ID:
        print("错误: TOKEN 或 CHAT_ID 未设置")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    try:
        requests.get(url, timeout=10)
    except Exception as e:
        print(f"发送 Telegram 失败: {e}")

def get_rsi(symbol):
    try:
        # 增加容错：抓取 2 个月数据以确保有足够的收盘价计算 RSI
        df = yf.download(symbol, period="2mo", interval="1d", progress=False)
        if df.empty or len(df) < 15: 
            return None
        # 计算 14 日 RSI
        rsi_series = ta.rsi(df["Close"], length=14)
        if rsi_series is None or rsi_series.empty:
            return None
        return rsi_series.iloc[-1]
    except Exception as e:
        print(f"无法计算 {symbol} 的 RSI: {e}")
        return None

def check_stocks():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始马股扫描...")
    has_alert = False
    
    for symbol, criteria in WATCHLIST.items():
        try:
            stock = yf.Ticker(symbol)
            # 核心修复：检查 info 是否有效
            info = stock.info
            if not info or 'currentPrice' not in info:
                print(f"⚠️ 跳过 {symbol}: 接口未返回数据 (可能代码不匹配或 Yahoo 维护)")
                continue
            
            # 安全地提取各项指标
            current_price = info.get("currentPrice")
            pe_ratio = info.get("trailingPE")
            
            # 处理股息率：如果是 None 则设为 0
            raw_div = info.get("dividendYield")
            div_yield = (raw_div * 100) if raw_div is not None else 0
            
            rsi_val = get_rsi(symbol)
            
            # 触发判断
            triggers = []
            if pe_ratio and pe_ratio <= criteria["target_pe"]:
                triggers.append(f"✅ PE低估: {pe_ratio:.2f} (目标:{criteria['target_pe']})")
            
            if div_yield >= criteria["min_div"] and criteria["min_div"] > 0:
                triggers.append(f"💰 高股息: {div_yield:.2f}% (目标:>{criteria['min_div']}%)")
            
            if rsi_val is not None and rsi_val <= 30:
                triggers.append(f"📉 RSI超卖: {rsi_val:.2f} (买入机会)")

            if triggers:
                has_alert = True
                msg = (f"🌟【马股预警】{criteria['name']} ({symbol})\n"
                       f"股价: RM {current_price}\n"
                       f"-------------------\n"
                       f"{'\n'.join(triggers)}\n"
                       f"-------------------\n"
                       f"请核实基本面后决策。")
                send_telegram_msg(msg)
                print(f"提醒已发送: {criteria['name']}")

        except Exception as e:
            print(f"❌ 处理 {symbol} 时发生未知错误: {e}")
            continue

    if not has_alert:
        print("今日无符合买入条件的股票。")
        # 如果你想确认脚本确实运行了，可以取消下面这行的注释
        # send_telegram_msg("✅ 今日马股扫描完成，暂无触发信号。")

if __name__ == "__main__":
    check_stocks() # GitHub Actions 模式下只需运行一次
