# Beispiele
Für diese Beispiele die Datei environment_template.py in environment.py umbenennen und die Trade Republic Login Datein eintragen.

# Skripte
Folgende Skripte bilden ein Workspace um Aktien und Transaktionen von Trade Republic abzurufen und zu verarbeiten.

## portfolioExporter.py
Liest das aktuelle Portfolio von TR aus und speichert dieses als myPortfolio.json ab.

## timelineExporter.py
Speichert die komplette Timeline in myTimeline.json ab.

## isinDownloader.py
Kann verwendet werden um die Stock Details abzufragen. Jede ISIN wird in einem Unterordner stock_details mit der ISIN als JSON Datei abgelegt.

usage: isinDownloader.py [-h] [-i ISIN] [-f FILE] [-p] [-c]

optional arguments:
  -h, --help            show this help message and exit
  -i ISIN, --isin ISIN  Crawl single ISIN
  -f FILE, --file FILE  Crawl a list of ISINs
  -p, --portfolio       Crawl all stocks from myPortfolio.json
  -c, --combine         Combine all stock data to a single JSON file

```bash
python3 isinDownloader.py -i US72919P2020
python3 isinDownloader.py -f isins.txt
```

Ist bereits die Portfolio Datei heruntergeladen, so können alle Aktien im Portfolio mit folgendem Befehl abgefragt werden:
```bash
python3 isinDownloader.py -p
```

Folgender Befehl erstellt eine einzelne allStocks.json Datei, welche alle heruntergeladenen ISINs kombiniert.
```bash
python3 isinDownloader.py -c
```

## timelineCsvConverter.py
Konvertiert die Timeline in ein CSV Format. Damit dieses Skript richtig arbeitet, müssen alle gehandelten Aktien mit dem ISIN Downloader heruntergeladen sein.

*ACHTUNG:* Einige Aktien heißen bei Lang und Schwarz anders, als in der Trade Republic App. Außerdem verwendet Trade Republic selbst zum Teil unterschiedliche Namen. Es kann vorkommen, dass nicht zu jeder Aktie die ISIN automatisch zugeordnet wird. In diesem Fall wird ein Fehler ausgegeben und die ISIN muss manuell in die CSV Datei kopiert werde.

Der Export wurde für Portfolio Performance optimiert. Aktuell werden folgende Transaktionen verarbeitet:
- Einzahlung
- Kauf
- Sparplan Ausführung
- Verkauf
- Dividende
