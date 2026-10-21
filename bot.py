import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

# ====== PARAMETRES (adapte-les) ======
SYMBOL = "GC=F"              # garde ton symbole actuel
INTERVAL_MIN = 5             # taille de la bougie
MAX_AGE_MIN = 45             # on regarde les bougies fermees depuis <= 45 min
SESSION = (6, 20)            # session heure du Maroc
TZ_LOCAL = ZoneInfo("Africa/Casablanca")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# =====================================


def find_signal(df, now, max_age_min=MAX_AGE_MIN, interval_min=INTERVAL_MIN):
    """Retourne (side, ts, price, age_min) du croisement EMA20/50 le plus recent, sinon None."""
    close = df["Close"].astype(float).dropna()
    if len(close) < 210:
        print("pas assez de donnees", len(close))
        return None

    idx = close.index
    idx = idx.tz_convert("UTC") if idx.tz is not None else idx.tz_localize("UTC")
    close.index = idx

    # on ne garde que les bougies deja fermees (la derniere peut etre en cours)
    closed_at = idx + timedelta(minutes=interval_min)
    close = close[closed_at <= now]
    closed_at = close.index + timedelta(minutes=interval_min)

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()

    last_age = (now - closed_at[-1]).total_seconds() / 60
    print(f"derniere bougie fermee: {close.index[-1]} (age {last_age:.1f} min)")

    # du plus recent au plus ancien
    for k in range(len(close) - 1, 0, -1):
        age = (now - closed_at[k]).total_seconds() / 60
        if age > max_age_min:
            break
        c = close.iloc[k]
        buy = ema20.iloc[k - 1] <= ema50.iloc[k - 1] and ema20.iloc[k] > ema50.iloc[k] and c > ema200.iloc[k]
        sell = ema20.iloc[k - 1] >= ema50.iloc[k - 1] and ema20.iloc[k] < ema50.iloc[k] and c < ema200.iloc[k]
        if buy or sell:
            return ("BUY" if buy else "SELL", close.index[k], float(c), age)
    return None


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=15,
    )
    print("telegram:", r.status_code, r.text[:200])
    r.raise_for_status()  # le run devient rouge si l'envoi echoue


def main():
    now = datetime.now(timezone.utc)
    local = now.astimezone(TZ_LOCAL)
    if not (SESSION[0] <= local.hour < SESSION[1]):
        print("hors session", local.strftime("%H:%M"))
        return

    df = yf.download(SYMBOL, period="5d", interval=f"{INTERVAL_MIN}m", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty:
        print("pas de donnees yfinance")
        return

    sig = find_signal(df, now)
    if sig is None:
        print("pas de signal")
        return

    side, ts, price, age = sig
    ts_local = ts.tz_convert(TZ_LOCAL).strftime("%H:%M")
    send_telegram(f"{side} {SYMBOL} @ {price:.2f}\nbougie {ts_local} (heure Maroc), il y a {age:.0f} min")


if __name__ == "__main__":
    main()

