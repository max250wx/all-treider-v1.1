"""Агрегация M1-данных в M5 через pandas resample."""

import pandas as pd


def m1_to_m5(in_csv, out_csv):
    df = pd.read_csv(in_csv, parse_dates=True, index_col=0)
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    df = df[df["Volume"] > 0].sort_index()

    agg = {"Open": "first", "High": "max", "Low": "min",
           "Close": "last", "Volume": "sum"}

    df_m5 = df.resample("5min").agg(agg).dropna()
    df_m5 = df_m5[df_m5["Volume"] > 0]

    df_m5.to_csv(out_csv)
    print(f"{in_csv} → {out_csv}")
    print(f"  было:  {len(df)} M1-баров")
    print(f"  стало: {len(df_m5)} M5-баров")
    print(f"  период: {df_m5.index[0]} — {df_m5.index[-1]}")
    print(f"  цена:   {df_m5['Close'].min():.3f} … {df_m5['Close'].max():.3f}")
    print()
    return df_m5


if __name__ == "__main__":
    m1_to_m5("ngu6_m1.csv", "ngu6_m5.csv")
    m1_to_m5("ng_m1.csv",   "ng_m5.csv")      # ← было ngv6_m1.csv
    m1_to_m5("br_m1.csv",   "br_m5.csv")