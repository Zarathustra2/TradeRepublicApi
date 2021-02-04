## Trade Republic api

This is an unofficial trade republic api as the previous owner has
made his repo private.

This is meant to be a follow up repo, more features to be added in the future.

Currently, this can be used to try out algorithmic trading
or learning how to process a lot of data.

TradeRepublic only allows one device to be registered at the same time.
So if you are currently logged in on your phone it will log you out from your phone.

Also running it the first time will likely error but then running it for the second
time will work. Have to debug this but not much time.

## Example
```python3

def process(json_data):
    print("I am a processor: ", json_data)

async def main():
    tr = TRApi(NUMBER, PIN)
    tr.login()

    # Each callback can be specified 
    # if wanted, default is print
    await tr.cash(callback=lambda x: print(f"Cash data: {x}"))
    await tr.portfolio()

    isin = "US62914V1061"
    await tr.derivativ_details(isin)
    await tr.stock_details(isin)
    await tr.ticker(isin, callback=process)
    await tr.news(isin) 
    
    await tr.start()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
```