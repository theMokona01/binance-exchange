#!/usr/bin/env python

import asyncio
from binance import AsyncClient, BinanceSocketManager
import pandas as pd
import nest_asyncio
nest_asyncio.apply()
import ta
import urllib.parse
import hashlib
import hmac
import base64
import requests
import time
import json
from binance import Client
from cred import KEY, SECRET

import warnings
warnings.simplefilter('ignore')

api_url = "https://api.binance.us"

# get binanceus signature
def get_binanceus_signature(data, secret):
    postdata = urllib.parse.urlencode(data)
    message = postdata.encode()
    byte_key = bytes(secret, 'UTF-8')
    mac = hmac.new(byte_key, message, hashlib.sha256).hexdigest()
    return mac

# Attaches auth headers and returns results of a POST request
def binanceus_request(uri_path, data, api_key, api_sec):
    headers = {}
    headers['X-MBX-APIKEY'] = api_key
    signature = get_binanceus_signature(data, api_sec) 
    payload={
        **data,
        "signature": signature,
        }           
    req = requests.post((api_url + uri_path), headers=headers, data=payload)
    return req.text


def createframe(msg):
    df = pd.DataFrame([msg])
    df = df.loc[:, ['s', 'E', 'p']]
    df.columns = ['symbol', 'Time', 'Price']
    df.Price = df.Price.astype(float)
    df.Time = pd.to_datetime(df.Time, unit='ms')
    return df


async def main():
    api_key=KEY
    secret_key=SECRET
    df = pd.DataFrame()
    open_position = False

    client = await AsyncClient.create(tld='us')
    bm = BinanceSocketManager(client)

    # start any sockets here, i.e a trade socket
    ts = bm.trade_socket('ETHUSD')

    # then start receiving messages
    async with ts as tscm:
        while True:
            res = await tscm.recv()
            df = df.append(createframe(res))
            if len(df) > 30:
                if not open_position:

                    if ta.momentum.roc(df.Price, 30).iloc[-1] > 0 and \
                        ta.momentum.roc(df.Price, 30).iloc[-2]: #enter the position

                        symbol="ETHUSD"
                        side="BUY"
                        type="MARKET"
                        quantity="0.1"

                        uri_path = "/api/v3/order"
                        data = {
                            "symbol": symbol,
                            "side": side,
                            "type": type,
                            "quantity": quantity,
                            "timestamp": int(round(time.time() * 1000)) 
                        }

                        order= binanceus_request(uri_path, data, api_key, secret_key)

                        #order = client.create_order(symbol='BNBUSD', side='BUY',
                        #type='MARKET', quantity=0.1)

                        open_position=True
                        print(order)
                        order = json.loads(order)
                        buyprice = float(order["fills"][0]["price"])
                    
                if open_position: 
                    subdf = df[df.Time >= pd.to_datetime(order['transactTime'], unit='ms')]
                    if len(subdf) > 1:
                        subdf['highest'] = subdf.Price.cummax()
                        subdf['trailingstop'] = subdf['highest'] * 0.995
                        #trading stop condition
                        if subdf.iloc[-1].Price < subdf.iloc[-1].trailingstop or \
                            df.iloc[-1].Price / float(order["fills"][0]["price"]) > 1.002: #place sending order
                            

                            symbol="ETHUSD"
                            side="SELL"
                            type="MARKET"
                            quantity="0.1"

                            uri_path = "/api/v3/order"
                            data = {
                                "symbol": symbol,
                                "side": side,
                                "type": type,
                                "quantity": quantity,
                                "timestamp": int(round(time.time() * 1000)) 
                            }

                            order = binanceus_request(uri_path, data, api_key, secret_key)
                            #order = client.create_order(symbol = 'BNBUSD', side='SELL', type = 'MARKET', quantity=0.01)

                            print(order)
                            order = json.loads(order)
                            sellprice = float(order["fills"][0]["price"])
                            print(f'You made {(sellprice - buyprice)/buyprice} profit')

                            open_position = False

            print(df.iloc[-1])

    await client.close_connection()

if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

