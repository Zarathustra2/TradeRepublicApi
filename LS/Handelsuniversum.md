# Lang und Schwarz
Das Lang und Schwarz Handelsuniversum kann unter folgendem Link eingesehen werden.
https://www.ls-x.de/de/handelsuniversum

# PDF Konvertierung
Das Handelsuniversum wird als PDF zur Verfügung gestellt. Dieses kann mittels der Software Tabula in JSON und CSV konvertiert werden. Das Skript convert-stammdaten.py erzeugt ein JSON Array mit den wichtigsten Informationen.
Die Elemente sind WKN, ISIN, Name, Symbol
```json
[
	[
		"554550",
		"DE0005545503",
		"1+1 DRILLISCH AG O.N.",
		"DRI"
	],
    ...
	[
		"A0LEPS",
		"FR0010285965",
		"1000MERCIS INH.EO-,10",
		"XXX"
	]
]
```
