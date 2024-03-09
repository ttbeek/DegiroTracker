import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
import numpy as np
from math import floor, ceil
from seaborn import color_palette

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from locale import setlocale, LC_TIME

from requests import get
from http.client import HTTPSConnection
from io import StringIO
from browser_cookie3 import chrome

from csv import QUOTE_NONNUMERIC
from os import _exit
from pyuac import isUserAdmin, runAsAdmin
from time import mktime
from pandas import merge, DataFrame, read_csv, to_numeric
from functools import reduce

setlocale(LC_TIME, 'nl_NL.UTF-8')


SMALL_FONT_SIZE = 14
MEDIUM_FONT_SIZE = 20
BIGGER_FONT_SIZE = 30

NUMBER_OF_BINS = 100

plt.style.use('seaborn-v0_8')
plt.rc('font', size=SMALL_FONT_SIZE)          # controls default text sizes
plt.rc('axes', titlesize=MEDIUM_FONT_SIZE)     # fontsize of the axes title
plt.rc('axes', labelsize=MEDIUM_FONT_SIZE)    # fontsize of the x and y labels
plt.rc('xtick', labelsize=SMALL_FONT_SIZE)    # fontsize of the tick labels
plt.rc('ytick', labelsize=SMALL_FONT_SIZE)    # fontsize of the tick labels
plt.rc('legend', fontsize=MEDIUM_FONT_SIZE)   # legend fontsize
plt.rc('figure', titlesize=BIGGER_FONT_SIZE)  # fontsize of the figure title


STORTING_TRANSACTIES = [
    "iDEAL storting",
    "Terugstorting",
    "Processed Flatex Withdrawal",
    "Reservation iDEAL / Sofort Deposit",
    "iDEAL Deposit",
    "Processed Flatex Withdrawal",
    "flatex terugstorting"]


BASE_URL = "trader.degiro.nl"


class DegiroReciever():
    def __init__(self):
        if not Path("data").exists():
            Path("data").mkdir()
        if not Path("data\\portfolio").exists():
            Path("data\\portfolio").mkdir()


    def get_session(self):
        if not isUserAdmin():
            try:
                runAsAdmin(wait=False)
            except:
                raise Exception("Geen verslagen kunnen ophalen. Sta open het programma in 'admin' modus")
            _exit(1)
        
        cookie_jar = chrome(domain_name=BASE_URL)
        for cookie in cookie_jar:
            if cookie.name == "JSESSIONID":
                return cookie.value
        raise Exception("Geen verslagen kunnen ophalen. Controleer of je ingelogd bent op Degiro in Google Chrome!")


    def get_report(self, report, date=None):
        if report == "positionReport":
            # print(date.strftime("%d-%m-%Y"))
            day, month, year = datetime.strftime(date, "%d-%m-%Y").split("-")
            url = f"/reporting/secure/v3/{report}/csv?sessionId={self.session_id}&country=NL&lang=nl&toDate={day}/{month}/{year}"
        else:
            print(f"Ophalen '{report}'...")
            day, month, year = datetime.strftime(datetime.now(), "%d-%m-%Y").split("-")
            url = f"/reporting/secure/v3/{report}/csv?sessionId={self.session_id}&country=NL&lang=nl&fromDate=01/01/2000&toDate={day}/{month}/{year}"

        conn = HTTPSConnection(BASE_URL)
        conn.request("GET", url, "", {})

        res = conn.getresponse()
        data = res.read().decode("utf-8")
        return data


    def reports_up_to_date(self):
        date_formatted = (datetime.now() - timedelta(1)).strftime("%d-%m-%Y")
        return Path(f"data\\portfolio\\Portfolio {date_formatted}.csv").exists()


    def save_portfolio_reports(self, date):
        print("Ophalen dagverslagen...\n")
        while date < datetime.now() - timedelta(1):
            date_string = datetime.strftime(date, "%d-%m-%Y")
            if not Path(f"data\\portfolio\\Portfolio {date_string}.csv").exists():
                data = self.get_report("positionReport", date)
                portfolio_report = read_csv(StringIO(data), sep=",")  
                portfolio_report.to_csv(f"data\\portfolio\\Portfolio {date_string}.csv", sep=";", index=False, quoting=QUOTE_NONNUMERIC)

            date += timedelta(1)


    def save_reports(self):
        if self.reports_up_to_date():
            return
        
        print("Ophalen verslagen...")
        self.session_id = self.get_session()
        # Transaction report
        data = self.get_report("transactionReport")
        report = read_csv(StringIO(data), sep=",")
        report.to_csv(f"data\\transactions.csv", sep=";", index=False, quoting=QUOTE_NONNUMERIC)

        # Cash report
        data = self.get_report("cashAccountReport")
        report = read_csv(StringIO(data), sep=",")  
        report.to_csv(f"data\\cash.csv", sep=";", index=False, quoting=QUOTE_NONNUMERIC)

        # Portfolio reports
        self.save_portfolio_reports(self.get_start_date())


    def get_start_date(self):
        cash_report = read_csv("data\\cash.csv", sep=";")
        transactions_report = read_csv("data\\transactions.csv", sep=";")
        cash_report_start = datetime.strptime(cash_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        transaction_report_start = datetime.strptime(transactions_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        return min(cash_report_start, transaction_report_start)


def safe_division(x, y):
    return x / y if y else 0


class DegiroProcessor():
    def __init__(self) -> None:
        self.cash_report = read_csv("data\\cash.csv", sep=";")
        self.transactions_report = read_csv("data\\transactions.csv", sep=";")


    def get_start_date(self):
        cash_report_start = datetime.strptime(self.cash_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        transaction_report_start = datetime.strptime(self.transactions_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        return min(cash_report_start, transaction_report_start)


    def process_stats(self):
        print("Verslagen verwerken...")
        start_date = self.get_start_date()
        date = start_date

        deposited = 0
        costs = 0
        previous_result = 0

        values_df = DataFrame(columns=["Datum"])
        stats = []
        while date < datetime.now() - timedelta(1):
            try:
                date_formatted = date.strftime("%d-%m-%Y")

                cash_transactions = self.cash_report[self.cash_report["Datum"] == date_formatted]
                for cash_transaction in cash_transactions.itertuples():
                    if "transactiekosten" in cash_transaction.Omschrijving.lower():
                        costs += cash_transaction._9

                    elif any(deposit_transaction in cash_transaction.Omschrijving for deposit_transaction in STORTING_TRANSACTIES):
                        deposited += cash_transaction._9

                try:
                    value_report = read_csv(f"data\\portfolio\\Portfolio {date_formatted}.csv", sep=";")
                except Exception as e:
                    date += timedelta(1)
                    print(e)
                    continue

                values_day = {}
                values_day["Datum"] = [date_formatted]

                for row in value_report.itertuples():
                    if row._6 != "0,00":
                        values_day[row.Product] = [row._6.replace(",", ".")]

                values_df = values_df.merge(DataFrame.from_dict(values_day), how="outer")

                cash_total = sum([float(row["Waarde in EUR"].replace(",", ".")) for index, row in value_report.iterrows() if "CASH & CASH FUND & FTX CASH" in row["Product"]])

                value_total = sum([float(value.replace(",", ".")) for value in list(value_report["Waarde in EUR"])])
                result_total = value_total - deposited - costs
                result_percentage = safe_division(result_total, value_total - result_total) * 100
                daily_result_total = result_total - previous_result
                daily_result_percentage = safe_division(daily_result_total, value_total - daily_result_total - cash_total) * 100

                stats.append([
                    date_formatted, 
                    round(value_total, 2), 
                    round(deposited, 2), 
                    round(costs, 2), 
                    round(result_total, 2), 
                    round(result_percentage, 2), 
                    round(daily_result_total, 2), 
                    round(daily_result_percentage, 2)
                ])
                date += timedelta(1)
                previous_result = result_total
                
            except Exception as e:
                date += timedelta(1)
                print(e)

        stats_df = DataFrame(data=stats, columns=["Datum", "Waarde", "Inleg", "Kosten", "Rendement", "Rendement(%)", "Dagelijks rendement", "Dagelijks rendement(%)"])
        for column in set(values_df.columns) - {"Datum"}:
            values_df[column] = to_numeric(values_df[column], errors="coerce")
        
        values_df.to_csv("Degiro - Waarde.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Waarde' opgeslagen!")
        stats_df.to_csv("Degiro - Rendement.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Rendement' opgeslagen!")


def get_month(datum:date):
    maand_naam = datum.strftime("%B")
    return datum.year, maand_naam

class DegiroTransactions():
    def __init__(self):
        self.cash_report = read_csv("data/transactions.csv", sep=";")
        self.start_datum = datetime.strptime(self.cash_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")

    def process_transactions(self):
        aankopen = []
        transacties = {}
        for _, row in self.cash_report.iterrows():
            maand = get_month(datetime.strptime(row["Datum"], "%d-%m-%Y"))

            if not maand in transacties:
                transacties[maand] = {"Koop": 0, "Verkoop": 0}

            type_transactie = "Koop" if row["Aantal"] > 0 else "Verkoop"
            transacties[maand][type_transactie] += abs(row["Waarde"])

        datum = self.start_datum - timedelta(1)
        while datum < datetime.now() - timedelta(1):
            datum += timedelta(1)
            
            maand = get_month(datum)
            if maand in [(aankoop[0], aankoop[1]) for aankoop in aankopen]:
                continue
            
            if maand in transacties:
                aankopen.append([
                    *maand, 
                    round(transacties[maand]["Koop"], 2), 
                    round(transacties[maand]["Verkoop"], 2), 
                    round(transacties[maand]["Koop"] - transacties[maand]["Verkoop"], 2)])
                continue
            aankopen.append([*maand, 0, 0, 0])

        aankopen_df = DataFrame(data=aankopen, columns=["Jaar", "Maand", "Koop", "Verkoop", "Netto"])
        aankopen_df.to_csv("Degiro - Transacties.csv", sep=";", decimal=",", index=False)
        print("Verslag 'Degiro - Transacties' opgeslagen!")


@dataclass
class Dividend:
    datum:date
    stock:str
    amount:float
    currency:str
    exchange:float=0
    amount_eur:float=0
    belasting:float=0
    aandelen_waarde:float=0
    percentage:float=0


def get_last_date(datum:date):
    next_month = datum.replace(day=28) + timedelta(4)
    return next_month - timedelta(days=next_month.day)


def get_next_month(datum:date):
    next_month = datum.replace(day=28) + timedelta(4)
    return next_month - timedelta(days=next_month.day-1)


def same_month(date1:date, date2:date):
    if date1.year == date2.year and date1.month == date2.month:
        return True
    return False


def get_exchange(date:date, stock:str, valuta:str):
    date_formatted = date.strftime("%d-%m-%Y")
    value_report = read_csv(f"data\\portfolio\\Portfolio {date_formatted}.csv", sep=";")
    records = value_report[value_report["Product"] == stock]

    if len(records) == 0:
        return get_exchange(date - timedelta(days=1), stock, valuta)

    record = records.iloc[0]
    waarde_eur = float(record["Waarde in EUR"].replace(",", "."))
    waarde_lokaal = float(record["Lokale waarde"].split(" ")[-1])
    exchange = waarde_lokaal / waarde_eur

    if record["Lokale waarde"].split(" ")[0] != valuta:
        df_valuta = value_report[value_report["Lokale waarde"].str.contains(valuta)]
        if len(df_valuta) == 0:
            return 1, waarde_eur
        record = df_valuta.loc[df_valuta["Waarde in EUR"].idxmax()]
        waarde_lokaal = float(record["Lokale waarde"].split(" ")[-1])

        exchange = waarde_lokaal / float(record["Waarde in EUR"].replace(",", "."))
    return exchange, waarde_eur


class DegiroDividend:
    def __init__(self):
        self.cash = read_csv("data\\cash.csv", sep=";")


    def get_belasting(self, stock:str, datum:str):
        record = self.cash[(self.cash["Omschrijving"] == "Dividendbelasting") &
                    (self.cash["Product"] == stock) & 
                    (self.cash["Datum"] == datum)]
        if len(record) == 0:
            return 0
        return abs(record.iloc[0]["Unnamed: 8"])
  

    def get_dividends(self):
        self.dividends = []
        for _, row in self.cash[self.cash["Omschrijving"] == "Dividend"].iterrows():
            datum = datetime.strptime(row["Datum"], "%d-%m-%Y").date()

            dividend = Dividend(
                datum=datum,
                stock=row["Product"],
                amount=row["Unnamed: 8"],
                currency=row["Saldo"])

            try:
                dividend.belasting = self.get_belasting(dividend.stock, dividend.datum.strftime("%d-%m-%Y"))
            except:
                print(f"Waarschuwing: Bij het dividend van '{dividend.stock}' kon de dividendbelasting niet gevonden worden.")

            try:
                dividend.exchange, dividend.aandelen_waarde = get_exchange(dividend.datum, dividend.stock, dividend.currency)
            except:
                print(f"Waarschuwing: Bij het dividend van '{dividend.stock}' is geen positie gevonden.")
                print("              Hierdoor is niet kunnen controleren wat de waarde van de positie is.")
                dividend.exchange, dividend.aandelen_waarde = 1, dividend.amount * 100

            dividend.amount_eur = (dividend.amount - dividend.belasting) / dividend.exchange
            dividend.percentage = dividend.amount_eur / dividend.aandelen_waarde * 100
            self.dividends.append(dividend)


    def dividend_verwerken(self):
        datum = min([dividend.datum for dividend in self.dividends])
        datum = get_last_date(datum)

        df_dividend = DataFrame(columns=["Jaar", "Maand"])
        df_betalingen = DataFrame(columns=["Jaar", "Maand"])

        dividend_totaal = {}
        belasting_totaal = 0

        while datum < datetime.now().date() - timedelta(1):
            maand_naam = datum.strftime("%B")

            dividend_totaal["Jaar"] = [datum.year]
            dividend_totaal["Maand"] = [maand_naam]

            betalingen = {}
            betalingen["Jaar"] = [str(datum.year)]
            betalingen["Maand"] = [maand_naam]
            betalingen["Dividendbelasting"] = 0

            dividend_dag = [dividend for dividend in self.dividends if same_month(dividend.datum, datum)]
            for dividend in dividend_dag:
                belasting_totaal += dividend.belasting / dividend.exchange
                betalingen["Dividendbelasting"] += dividend.belasting / dividend.exchange


                betalingen[dividend.stock] = [round(dividend.amount_eur, 3)]
                if dividend.stock in dividend_totaal.keys():
                    dividend_totaal[dividend.stock] = [round(dividend_totaal[dividend.stock][0] + dividend.amount_eur, 3)]
                else:
                    dividend_totaal[dividend.stock] = [round(dividend.amount_eur, 3)]

            # Betalingen regel toevoegen
            if len(dividend_dag) > 0:
                betalingen["Dividendbelasting"] = round(betalingen["Dividendbelasting"], 3)
                df_betalingen = df_betalingen.merge(DataFrame.from_dict(betalingen), how="outer")

            df_dividend = df_dividend.merge(DataFrame.from_dict(dividend_totaal), how="outer")
            datum = get_next_month(datum)

        # Totaal regel toevoegen aan betalingen
        dividend_totaal["Jaar"] = ["Totaal"]
        dividend_totaal["Maand"] = [""]
        dividend_totaal["Dividendbelasting"] = belasting_totaal
        df_betalingen = df_betalingen.merge(DataFrame.from_dict(dividend_totaal), how="outer")

        dividend_list = [[dividend.datum, 
                        dividend.stock, 
                        round(dividend.amount_eur, 3), 
                        round(dividend.percentage, 3), 
                        round(dividend.belasting / dividend.exchange, 3)]
                        for dividend in self.dividends]

        df_lijst = DataFrame(data=dividend_list, columns=["Datum", "Product", "Dividend", "Percentage", "Belasting"])
        df_lijst.to_csv("Degiro - Dividend - Overzicht.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Dividend - Overzicht' opgeslagen!")
        df_dividend.to_csv("Degiro - Dividend - Totaal.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Dividend - Totaal' opgeslagen!")
        df_betalingen.to_csv("Degiro - Dividend - Betalingen.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Dividend - Betalingen' opgeslagen!\n")


    def dividend_overview(self):
        self.get_dividends()
        self.dividend_verwerken()


def get_prev_date(datum:date, values:dict):
    if datum in values.keys():
        return datum
    return get_prev_date(datum - timedelta(1), values)


def get_data(start, end, ticker):
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d&includePrePost=true&events=split"
    res = get(url, headers={"Connection": "keep-alive", "Accept-Encoding": "gzip, deflate, br", "Accept": "*/*", "User-Agent": "python"})
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
    return DataFrame(data=tracked_data)


def get_ticker_data(start:date, end:date, tickers=["%5EGSPC", "%5EIXIC"]):
    start_timestamp = int(mktime((start-timedelta(10)).timetuple()))
    end_timestamp = int(mktime(end.timetuple()))

    tracked_tickers = []
    for ticker in tickers:
        values = get_data(start_timestamp, end_timestamp, ticker)
        tracked_data = get_tracking(start, end, values, ticker)
        tracked_tickers.append(tracked_data)

    df_merged = reduce(lambda  left,right: merge(left,right,on=['Datum'], how='outer'), tracked_tickers).fillna(0)
    return df_merged


def process_column_name(column:str):
    def remove_end(name:str, end:list[str]):
        for i in end:
            name = name.rsplit(maxsplit=1)[0] if name.rsplit(maxsplit=1)[-1] == i else name
        return name
    
    column = column.replace("-", "").strip().replace("CASH & CASH FUND & FTX ", "")
    column = "".join(column.split(" INC")[:-1] or column)
    return remove_end(column, ["LTD", "C", "IN"])


class DegiroGraphs():
    def __init__(self):
        if not Path("graphs").exists():
            Path("graphs").mkdir()
        
        self.values_df = read_csv(f"Degiro - Waarde.csv", sep=";", na_values=0, decimal=",")
        self.stats_df = read_csv(f"Degiro - Rendement.csv", sep=";", decimal=",")
        self.aankopen_df = read_csv(f"Degiro - Transacties.csv", sep=";", decimal=",")

        if not Path(f"Degiro - Waarde.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro - Waarde.csv' bestaat.")
        if not Path(f"Degiro - Rendement.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro - Rendement.csv' bestaat.")
        if not Path(f"Degiro - Transacties.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro - Transacties.csv' bestaat.")


    def make_stacked_value_plot(self,
                                plot_path:Path,
                                start_date=date(2000,1,1),
                                end_date=datetime.now().date()):
        
        if plot_path.exists() and end_date.year != datetime.now().year:
            return
        
        # Select data to plot
        dates = self.values_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        conditions = [date.date() >= start_date and date.date() <= end_date for date in dates]

        dates_selection = [date for date, condition in zip(dates, conditions) if condition]
        values_selection = self.values_df[conditions].drop('Datum', axis=1).dropna(axis=1, how="all").fillna(0)
        values_selection = values_selection.reindex(sorted(values_selection.columns), axis=1)
        columns_selection = [process_column_name(column) for column in values_selection.columns]

        # Create figure
        fig, ax = plt.subplots(figsize=(50, 15))
        fig.suptitle(plot_path.stem)
        fig.subplots_adjust(left=0.029, right=0.79, top=0.94, bottom=0.053)

        # Plot data
        col = color_palette("gist_rainbow", len(values_selection.columns))
        #seismic
        #cool
        #viridis
        #coolwarm
        #hsv
        #Spectral
        #rainbow
        #gist_rainbow
        #turbo
        ax.stackplot(dates_selection, values_selection.T, labels=columns_selection, colors=col)
        
        # Create legend
        ax.legend(loc="upper left", ncols=2, bbox_to_anchor=(1,1))

        # Set axis limits
        ax.set_xlim(min(dates_selection), max(dates_selection))
        ax.set_ylim(0)
        ax.axhline(y=0, color="black")

        # Set axis labels
        ax.set_xlabel("Datum")
        ax.set_ylabel("Waarde (Euro)")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: '€{:,.0f}'.format(x).replace(',', '.')))

        fig.savefig(plot_path, format="png", dpi=200)
        plt.close(fig)
        print(f"Grafiek '{plot_path.stem}' opgeslagen!")


    def make_scatterplot_daily_change(self,
                                      plot_path:Path,
                                      start_date=date(2000,1,1),
                                      end_date=datetime.now().date()):
        
        if plot_path.exists() and end_date.year != datetime.now().year:
            return
        
        # Select data to plot
        dates = self.stats_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        conditions = [date.date() >= start_date and date.date() <= end_date for date in dates]
        dates_selection = {index:date for index, (date, condition) in enumerate(zip(dates, conditions)) if condition}

        # Define data to plot
        c = list(dates_selection.keys())
        x = self.stats_df[conditions]["Dagelijks rendement(%)"]
        y = self.stats_df[conditions]["Dagelijks rendement"]

        # Create figure
        fig, ax = plt.subplots(figsize=(40, 15))
        fig.suptitle(plot_path.stem)
        fig.subplots_adjust(left=0.039, right=1.1, top=0.94, bottom=0.053)

        # Plot data
        plt.scatter(x=x, y=y, c=c, cmap="viridis")

        # Define color bar
        cbar = plt.colorbar(pad=0.015, ticks=np.linspace(min(c), max(c), 8))  # Adjust the number of ticks as needed
        cbar.ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda color_int, _: dates_selection[int(color_int)].strftime("%d-%m-%Y")))

        # Create lines at x=0 and y=0, as axis
        ax.axhline(y=0, color="black")
        ax.axvline(x=0, color="black")

        # Set plot labels
        ax.set_xlabel("Procentuele stijging (%)")
        ax.set_ylabel("Waardestijging (Euro)")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '€{:,.0f}'.format(c).replace(',', '.')))

        fig.savefig(plot_path, format="png", dpi=200)
        plt.close(fig)
        print(f"Grafiek '{plot_path.stem}' opgeslagen!")


    def make_profit_plot(self,
                         plot_path:Path,
                         start_date=date(2000,1,1),
                         end_date=datetime.now().date()):
        
        if plot_path.exists() and end_date.year != datetime.now().year:
            return
        
        # Select data to plot
        dates = self.stats_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        conditions = [date.date() >= start_date and date.date() <= end_date for date in dates]
        dates_selection = [date for date, condition in zip(dates, conditions) if condition]

        # Define data to plot
        values_selection = self.stats_df[conditions][["Datum","Waarde", "Inleg", "Rendement"]]
        values_selection["Datum"] = dates_selection

        # Create figure
        fig, ax = plt.subplots(figsize=(40, 15))
        fig.suptitle(plot_path.stem)
        fig.subplots_adjust(left=0.039, right=0.98, top=0.94, bottom=0.053)

        # Plot data
        ax.plot(dates_selection, values_selection[["Waarde", "Rendement", "Inleg"]], label=["Waarde", "Rendement", "Inleg"])

        # Create legend
        ax.legend(loc="upper left", ncols=3)

        # Set axis limits
        ax.set_xlim(min(dates_selection), max(dates_selection))
        minimale_y = min([min(values_selection["Waarde"]), min(values_selection["Rendement"]), min(values_selection["Inleg"])])
        if minimale_y < 0:
            ax.axhline(y=0, color="black")
            ax.set_ylim(minimale_y * 1.5)
        else:
            ax.set_ylim(0)

        # Set axis labels
        ax.set_xlabel("Datum")
        ax.set_ylabel("Waarde (Euro)")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '€{:,.0f}'.format(c).replace(',', '.')))

        fig.savefig(plot_path, format="png", dpi=200)
        plt.close(fig)
        print(f"Grafiek '{plot_path.stem}' opgeslagen!")


    def make_histogram_plot(self,
                            plot_path:Path,
                            kolom:str,
                            start_date=date(2000,1,1),
                            end_date=datetime.now().date()):

        if plot_path.exists() and end_date.year != datetime.now().year:
            return
        
        # Select data to plot
        dates = self.stats_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        conditions = [date.date() >= start_date and date.date() <= end_date and date.weekday() <= 4 for date in dates]

        # Define data to plot
        data = self.stats_df[conditions][kolom]

        # Create figure
        fig, ax = plt.subplots(figsize=(40, 15))
        fig.suptitle(plot_path.stem)
        fig.subplots_adjust(left=0.029, right=0.98, top=0.94, bottom=0.053)

        # Define bins
        binsize = (max(data) - min(data)) / NUMBER_OF_BINS
        min_bin = floor(min(data) / binsize) * binsize
        max_bin = ceil(max(data) / binsize) * binsize

        # Generate histogram data
        bins = list(np.arange(min_bin, max_bin + binsize, binsize))
        bins = [round(bin, 3) for bin in bins]
        hist, edges = np.histogram(data, bins=bins)
        edges = [edge + binsize/2 for edge in edges]
        colors = ['green' if number > 0 else 'red' for number in edges]

        # Create figure
        plt.bar(edges[:-1], hist, width=np.diff(edges), color=colors, edgecolor="black")

        # Set axis labels
        ax.set_xlabel("Rendement")
        ax.set_ylabel("Aantal dagen")
        ax.axhline(y=0, color="black")
        ax.set_xlim(min(bins), max(bins))

        if kolom == "Dagelijks rendement":
            ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '€{:,.0f}'.format(c).replace(',', '.')))
        elif kolom == "Dagelijks rendement(%)":
            ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '{:,.0f}%'.format(c).replace(',', '.')))

        fig.savefig(plot_path, format="png", dpi=200)
        plt.close(fig)
        print(f"Grafiek '{plot_path.stem}' opgeslagen!")


    def make_profit_line(self,
                         plot_path:Path,
                         start_date=date(2000,1,1),
                         end_date=datetime.now().date()):

        def track(row):
            self.tracked_percentage = self.tracked_percentage * (1 + row["Dagelijks rendement(%)"]/100)
            return self.tracked_percentage - 100
        
        self.tracked_percentage = 100
        if plot_path.exists() and end_date.year != datetime.now().year:
            return
        
        # Select data to plot
        dates = self.stats_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        conditions = [date.date() >= start_date and date.date() <= end_date for date in dates]
        dates_selection = [date for date, condition in zip(dates, conditions) if condition]

        tickers = {"S&P 500": "%5EGSPC", "NASDAQ": "%5EIXIC"}
        try:
            ticker_data = get_ticker_data(min(dates_selection).date(), max(dates_selection).date(), tickers=tickers.values())
        except Exception as e:
            ticker_data = DataFrame(data={"Datum": []}|{ticker: [] for ticker in tickers.values()})

        # Define data to plot
        values_selection = self.stats_df[conditions][["Datum", "Dagelijks rendement(%)"]]
        values_selection = values_selection.merge(ticker_data, on="Datum", how="left").fillna(0)
        values_selection["Datum"] = dates_selection
        values_selection["Rendement_tracked"] = values_selection.apply(track, axis=1)
 
        # Create figure
        fig, ax = plt.subplots(figsize=(40, 15))
        fig.suptitle(plot_path.stem)
        fig.subplots_adjust(left=0.039, right=0.98, top=0.94, bottom=0.053)

        # Plot data
        ax.plot(dates_selection, values_selection[["Rendement_tracked", *tickers.values()]], label=["Portfolio", *tickers.keys()])

        # Create legend
        ax.legend(loc="upper left", ncols=3)

        # Set axis limits
        ax.set_xlim(min(dates_selection), max(dates_selection))
        minimale_y = min(
            [min(values_selection["Rendement_tracked"])] + [min(values_selection[ticker]) for ticker in tickers.values()])
        if minimale_y < 0:
            ax.axhline(y=0, color="black")
            ax.set_ylim(min(minimale_y * 1.1, 5))
        else:
            ax.axhline(y=0, color="black")
            ax.set_ylim(-5)

        # Set axis labels
        ax.set_xlabel("Datum")
        ax.set_ylabel("Performance (%)")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '{:,.0f}%'.format(c).replace(',', '.')))

        fig.savefig(plot_path, format="png", dpi=200)
        plt.close(fig)
        print(f"Grafiek '{plot_path.stem}' opgeslagen!")


    def make_purchases_plot(self, plot_path:Path, jaar:int):
        if plot_path.exists() and jaar != datetime.now().year:
            return
        
        # Define data to plot
        data = self.aankopen_df
        if jaar:
            data = self.aankopen_df[self.aankopen_df["Jaar"] == jaar]

        # Create figure
        fig, ax = plt.subplots(figsize=(40, 15))
        fig.suptitle(plot_path.stem)
        fig.subplots_adjust(left=0.029, right=0.98, top=0.94, bottom=0.053)

        # Create figure
        width = 0.45
        plt.bar(np.arange(data.shape[0]) + width, data["Netto"], width=width, edgecolor="black", label="Netto aankopen")
        plt.bar(np.arange(data.shape[0]), data["Koop"], width=width, color="green", edgecolor="black", label="Aankopen")
        plt.bar(np.arange(data.shape[0]), 0-data["Verkoop"], width=width, color="red", edgecolor="black", label="Verkopen")
    
        # Set axis labels
        ax.set_xlabel("Maand")
        ax.set_ylabel("Netto aankopen (Euro)")
        ax.axhline(y=0, color="black")
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '€{:,.0f}'.format(c).replace(',', '.')))
        ax.set_xticks(np.arange(data.shape[0]) + width/2, data["Maand"])
        ax.legend(loc="upper left", ncols=3)

        fig.savefig(plot_path, format="png", dpi=200)
        plt.close(fig)
        print(f"Grafiek '{plot_path.stem}' opgeslagen!")


    def make_plots(self):
        """
        RuntimeWarning: More than 20 figures have been opened. 
        Figures created through the pyplot interface (`matplotlib.pyplot.figure`) 
        are retained until explicitly closed and may consume too much memory. 
        
        (To control this warning, see the rcParam `figure.max_open_warning`). Consider using `matplotlib.pyplot.close()`."""

        print("Grafieken maken...")     
        self.make_profit_plot(Path("graphs\\Portfolio - Rendement.png"))
        self.make_stacked_value_plot(Path("graphs\\Portfolio - Waarde.png"))
        self.make_profit_line(Path(f"graphs\\Portfolio - Performance.png"))
        self.make_scatterplot_daily_change(Path("graphs\\Veranderingen - Verhouding.png"))
        self.make_histogram_plot(Path("graphs\\Veranderingen - Procentueel.png"), "Dagelijks rendement(%)")
        self.make_histogram_plot(Path("graphs\\Veranderingen - Waarde.png"), "Dagelijks rendement")

        dates = self.values_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        for year in range(min(dates).year, max(dates).year + 1):
            if not Path(f"graphs\\{year}").exists():
                Path(f"graphs\\{year}").mkdir()

            self.make_profit_plot(
                Path(f"graphs\\{year}\\Portfolio - Rendement {year}.png"),
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_stacked_value_plot(
                Path(f"graphs\\{year}\\Portfolio - Waarde {year}.png"),
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_profit_line(
                Path(f"graphs\\{year}\\Portfolio - Performance {year}.png"), 
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_scatterplot_daily_change(
                Path(f"graphs\\{year}\\Veranderingen - Verhouding {year}.png"),
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_histogram_plot(
                Path(f"graphs\\{year}\\Veranderingen - Procentueel {year}.png"),
                "Dagelijks rendement(%)",
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_histogram_plot(
                Path(f"graphs\\{year}\\Veranderingen - Waarde {year}.png"),
                "Dagelijks rendement",
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_purchases_plot(
                Path(f"graphs\\{year}\\Transacties {year}.png"),
                year)
            
        print("Alle grafieken zijn opgeslagen!")
        print("Dit venster kan gesloten worden")


if __name__ == "__main__":
    try:
        # DegiroReciever().save_reports()
        DegiroProcessor().process_stats()
        DegiroTransactions().process_transactions()
        DegiroDividend().dividend_overview()
        DegiroGraphs().make_plots()
    except Exception as e:
        print("Error:", e)
    finally:
        input()

# pyinstaller --onefile --icon=pog.ico --name=degiro main.py