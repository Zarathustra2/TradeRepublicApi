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
    
    # This will open up 3,500 websocket connections
    # to TradeRepublic with each being a single 
    # trade able stock.
    for isin in TRApi.all_isins():

        # Default callback for the data is print
        # and here we use our custom callback
        await tr.ticker(isin, callback=process)
    
    await tr.start()

if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(main())
```