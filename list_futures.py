import requests

url = "https://iss.moex.com/iss/engines/futures/markets/forts/securities.json"
resp = requests.get(url).json()
sec = resp["securities"]
cols = sec["columns"]
rows = sec["data"]

df = __import__("pandas").DataFrame(rows, columns=cols)
# Ищем всё, что связано с индексом МосБиржи
index_futures = df[df["SECID"].str.contains("MX|IMOEX", na=False)]
print(index_futures[["SECID", "SHORTNAME", "LASTTRADEDATE"]].to_string())