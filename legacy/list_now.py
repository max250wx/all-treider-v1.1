import requests
import pandas as pd

url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
data = requests.get(url).json()["securities"]
df = pd.DataFrame(data["data"], columns=data["columns"])

# Все NG-контракты с указанием даты последней сделки
ng = df[df["SECID"].str.startswith("NG", na=False)]
print(ng[["SECID", "SHORTNAME", "LASTTRADEDATE"]].to_string())

# Проверим, есть ли сегодня свечи по NGV6 и NGZ6
for ticker in ["NGV6", "NGX6", "NGZ6"]:
    r = requests.get(
        f"https://iss.moex.com/iss/engines/futures/markets/forts/securities/{ticker}/candles.json",
        params={"from": "2026-10-10", "till": "2026-10-13", "interval": 1},
    ).json()
    rows = r["candles"]["data"]
    print(f"{ticker}: {len(rows)} свечей за 10-13 октября")