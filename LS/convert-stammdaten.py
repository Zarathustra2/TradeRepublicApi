import json

with open('./stammdaten.json', 'r') as f:
    data = json.loads(f.read())

stocks = []
counter = 0

first = True
for d in data:
    for stock in d["data"]:
        if first == True:
            first = False
            continue

        wkn = stock[0]["text"]
        isin = stock[1]["text"]
        name = stock[2]["text"]
        shortcode = stock[3]["text"]
        
        stocks.append([wkn, isin, name, shortcode])
        counter = counter + 1

with open('./isins.json', 'w') as f:
    json.dump(stocks, f)

print('Converted {0} stocks'.format(counter))