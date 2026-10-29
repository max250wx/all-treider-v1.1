import pandas as pd

df = pd.read_csv(r"C:\trader\data\history\imoexf_m1.csv", index_col=0, parse_dates=True)
df.columns = [c.lower() for c in df.columns]
df = df.rename(columns={"vol": "volume"})

c = df["close"]
tr = pd.concat([df["high"]-df["low"], (df["high"]-c.shift()).abs(), (df["low"]-c.shift()).abs()], axis=1).max(axis=1)
atr = tr.ewm(alpha=1/14, adjust=False).mean()
pct = atr / c * 100

print("Баров:", len(pct))
print("ATR% min:    {:.4f}%".format(pct.min()))
print("ATR% median: {:.4f}%".format(pct.median()))
print("ATR% max:    {:.4f}%".format(pct.max()))
print("Проходит ATR >= 0.5%:", (pct >= 0.5).sum(), "из", len(pct))
print("Проходит ATR 0.5..6%:", ((pct >= 0.5) & (pct <= 6.0)).sum())