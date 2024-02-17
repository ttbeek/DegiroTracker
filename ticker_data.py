import requests
from datetime import timedelta, datetime, date
import time
import pandas as pd
from functools import reduce


def get_prev_date(datum:date, values:dict):
    if datum in values.keys():
        return datum
    return get_prev_date(datum - timedelta(1), values)


def get_data(start, end, ticker):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d&includePrePost=true&events=split"
    res = requests.get(url, headers={"Connection": "keep-alive", "Accept-Encoding": "gzip, deflate, br", "Accept": "*/*", "User-Agent": "python"})
    json_data = res.json()["chart"]["result"][0]
    dates = [datetime.fromtimestamp(date).date() for date in json_data["timestamp"]]
    values = json_data["indicators"]["quote"][0]["close"]
    return {datum: value for datum, value in zip(dates, values)}


def get_tracking(start, end, values, ticker):
    datum = start
    tracked_data = {"Datum": [], ticker: []}
    tracked = 100
    while datum <= end:
        date_formatted = datum.strftime("%d-%m-%Y")
        if datum not in values.keys():
            percentage = 0
        else:
            prev_datum = get_prev_date(datum - timedelta(1), values)
            change = values[datum] - values[prev_datum]
            percentage = change / values[prev_datum] * 100

        tracked = tracked * (1 + percentage/100)

        tracked_data["Datum"] = tracked_data["Datum"] + [date_formatted]
        tracked_data[ticker] = tracked_data[ticker] + [tracked - 100]
        datum += timedelta(1)
    return pd.DataFrame(data=tracked_data)


def get_ticker_data(start:date, end:date, tickers=["%5EGSPC", "%5EIXIC"]):
    start_timestamp = int(time.mktime((start-timedelta(10)).timetuple()))
    end_timestamp = int(time.mktime(end.timetuple()))

    tracked_tickers = []
    for ticker in tickers:
        values = get_data(start_timestamp, end_timestamp, ticker)
        tracked_data = get_tracking(start, end, values, ticker)
        tracked_tickers.append(tracked_data)

    df_merged = reduce(lambda  left,right: pd.merge(left,right,on=['Datum'], how='outer'), tracked_tickers).fillna(0)
    return df_merged


if __name__ == "__main__":
    get_ticker_data(
        date(2024, 1, 1),
        date(2024, 2, 20))

