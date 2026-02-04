import os
import asyncio
import yfinance as yf
from telegram import Bot
from datetime import datetime

# --- CONFIGURATION FROM GITHUB SECRETS ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
USER_ID = os.getenv('TELEGRAM_CHAT_ID')

# Targets for February 2026
TARGETS = {
    "BTC-USD": 74000,
    "ETH-USD": 2100,
    "5176.KL": 2.55  # SUNREIT Support
}

async def main():
    bot = Bot(token=TOKEN)
    msg_parts = ["📊 **Portfolio Check-in**"]
    
    # 1. Check BTC/ETH
    for ticker in ["BTC-USD", "ETH-USD"]:
        price = yf.Ticker(ticker).fast_info['last_price']
        support = TARGETS[ticker]
        msg_parts.append(f"{'₿' if 'BTC' in ticker else 'Ξ'} {ticker.split('-')[0]}: ${price:,.2f}")
        
        if price <= support:
            msg_parts.append(f"🚨 **ACTION:** {ticker.split('-')[0]} hit support! Deploy RM 200.")

    # 2. Check SUNREIT (Dividend Window: Before Feb 16)
    sun_price = yf.Ticker("5176.KL").fast_info['last_price']
    msg_parts.append(f"🏢 SUNREIT: RM{sun_price:.2f}")
    
    # Urgent Buy Alert (Triggered between Feb 12 - Feb 15)
    today = datetime.now()
    if 12 <= today.day <= 15 and today.month == 2:
        msg_parts.append("⚠️ **URGENT:** Buy SUNREIT now to catch the Feb 16 Ex-Date!")

    # 3. Send Message
    async with bot:
        await bot.send_message(chat_id=USER_ID, text="\n".join(msg_parts), parse_mode='Markdown')

if __name__ == '__main__':
    asyncio.run(main())
