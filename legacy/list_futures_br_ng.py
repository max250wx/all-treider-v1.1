import requests
import pandas as pd

url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
data = requests.get(url).json()["securities"]
df = pd.DataFrame(data["data"], columns=data["columns"])

br = df[df["SECID"].str.startswith("BR", na=False)]
ng = df[df["SECID"].str.startswith("NG", na=False)]

print("=== Доступные фьючерсы на Brent (BR) ===")
print(br[["SECID", "SHORTNAME", "LASTTRADEDATE"]].to_string())
print()
print("=== Доступные фьючерсы на газ (NG) ===")
print(ng[["SECID", "SHORTNAME", "LASTTRADEDATE"]].to_string())