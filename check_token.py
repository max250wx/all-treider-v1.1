"""Диагностика токена: что лежит в файле orderflow_collector.py."""

with open("orderflow_collector.py", "r", encoding="utf-8") as f:
    content = f.read()

for line in content.split("\n"):
    if line.strip().startswith("TOKEN ="):
        print("Строка в файле:")
        print(repr(line))
        print("")

        try:
            token = line.split('"')[1]
        except IndexError:
            print("Кавычки не найдены!")
            break

        print("Длина токена:", len(token))
        print("Первые 10 символов:", repr(token[:10]))
        print("Последние 10:", repr(token[-10:]))
        print("")

        print("Есть ли кириллица в токене?")
        cyr = [c for c in token if "А" <= c <= "я" or c in "ёЁ"]
        if cyr:
            print("  ДА! Найдены:", cyr[:10])
        else:
            print("  нет — токен чистый")
        break
else:
    print("Строка TOKEN = ... не найдена в файле")