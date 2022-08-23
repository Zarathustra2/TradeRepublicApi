import getpass4 as getpass

# Trade Republic Login
NUMBER = "+491731234567"
PIN = ""

# Default to English if not specified when calling the API
LOCALE = "en"
CURRENCY = "EUR"

if not PIN:
    PIN = getpass.getpass("Pin:")