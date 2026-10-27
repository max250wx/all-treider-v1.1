"""Диагностика структуры ответа MOEX sitenews."""

import requests

url = "https://iss.moex.com/iss/sitenews.json"
params = {"iss.meta": "off", "limit": 5}
resp = requests.get(url, params=params, timeout=30)
data = resp.json()

print("Колонки sitenews:")
print(data["sitenews"]["columns"])
print()
print("Первая запись:")
print(data["sitenews"]["data"][0])
print()
print("Все записи (первые 3):")
for row in data["sitenews"]["data"][:3]:
    print(row)