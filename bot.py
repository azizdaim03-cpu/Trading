import os
import sys
from datetime import datetime, timezone, timedelta

import requests
import yfinance as yf

TOKEN = os.environ["TG_TOKEN"]
CHAT = os.environ["TG_CHAT_ID"]

SYMBOL = "GC=F"        # or: gold futures (proche de XAUUSD)
START_H, END_H = 0, 24  # heures UTC pendant lesquelles on envoie des signaux
ATR_MULT = 1.5
RR = 10 / 3             # TP = 3.33 x SL (comme 3% / 10%)
MAX_AGE_MIN = 10        # ignore les signaux plus vieux que ca


def send(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text},
        timeout=15,
    )
    print("telegram:", r.status_code)


def main():
    if "test" in sys.argv:
        send("Bot signaux XAUUSD khddam")
        return

    now = datetime.now(timezone.utc)
    if not (START_H <= now.hour < END_H):
        print("hors session")
        return

    df = yf.download(SYMBOL, period="5d", interval="5m",
                     progress=False, auto_adjust=True)
    if hasattr(df.columns, "levels"):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna()
    if len(df) < 210:
        print("pas assez de donnees")
        return

    close, high, low = df["Close"], df["High"], df["Low"]
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    prev_close = close.shift(1)
    tr = (high - low).combine((high - prev_close).abs(), max)
    tr = tr.combine((low - prev_close).abs(), max)
    atr = tr.rolling(14).mean()

    # la derniere bougie est en cours : on utilise la derniere FERMEE (-2)
    i, j = -2, -3
    ts = df.index[i]
    ts = ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")
    closed_at = ts + timedelta(minutes=5)
    age = (now - closed_at).total_seconds() / 60
    if age > MAX_AGE_MIN:
        print("bougie trop ancienne", age)
        return

    c = float(close.iloc[i])
    buy = ema20.iloc[j] <= ema50.iloc[j] and ema20.iloc[i] > ema50.iloc[i] and c > ema200.iloc[i]
    sell = ema20.iloc[j] >= ema50.iloc[j] and ema20.iloc[i] < ema50.iloc[i] and c < ema200.iloc[i]
    if not (buy or sell):
        print("pas de signal")
        return

    sl_dist = float(atr.iloc[i]) * ATR_MULT
    tp_dist = sl_dist * RR
    if buy:
        sl, tp, side = c - sl_dist, c + tp_dist, "BUY"
    else:
        sl, tp, side = c + sl_dist, c - tp_dist, "SELL"

    send(
        f"{side} XAUUSD (M5)\n"
        f"Entree: {c:.2f}\n"
        f"SL: {sl:.2f}\n"
        f"TP: {tp:.2f}\n"
        f"RR: 1:{RR:.1f}\n"
        f"Verifie le prix dyal l'broker qbel ma tdkhl."
    )


if __name__ == "__main__":
    main()
