import pandas as pd
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import locale 

locale.setlocale(locale.LC_TIME, 'nl_NL.UTF-8')


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
    value_report = pd.read_csv(f"data\\portfolio\\Portfolio {date_formatted}.csv", sep=";")
    records = value_report[value_report["Product"] == stock]

    if len(records) == 0:
        return get_exchange(date - timedelta(days=1), stock)

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
        self.cash = pd.read_csv("data\\cash.csv", sep=";")


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

            dividend.belasting = self.get_belasting(dividend.stock, dividend.datum.strftime("%d-%m-%Y"))
            dividend.exchange, dividend.aandelen_waarde = get_exchange(dividend.datum, dividend.stock, dividend.currency)

            dividend.amount_eur = (dividend.amount - dividend.belasting) / dividend.exchange
            dividend.percentage = dividend.amount_eur / dividend.aandelen_waarde * 100
            self.dividends.append(dividend)


    def dividend_verwerken(self):
        datum = min([dividend.datum for dividend in self.dividends])
        datum = get_last_date(datum)

        df_dividend = pd.DataFrame(columns=["Jaar", "Maand"])
        df_betalingen = pd.DataFrame(columns=["Jaar", "Maand"])

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
                df_betalingen = df_betalingen.merge(pd.DataFrame.from_dict(betalingen), how="outer")

            df_dividend = df_dividend.merge(pd.DataFrame.from_dict(dividend_totaal), how="outer")
            datum = get_next_month(datum)

        # Totaal regel toevoegen aan betalingen
        dividend_totaal["Jaar"] = ["Totaal"]
        dividend_totaal["Maand"] = [""]
        dividend_totaal["Dividendbelasting"] = belasting_totaal
        df_betalingen = df_betalingen.merge(pd.DataFrame.from_dict(dividend_totaal), how="outer")

        dividend_list = [[dividend.datum, 
                        dividend.stock, 
                        round(dividend.amount_eur, 3), 
                        round(dividend.percentage, 3), 
                        round(dividend.belasting / dividend.exchange, 3)]
                        for dividend in self.dividends]

        df_lijst = pd.DataFrame(data=dividend_list, columns=["Datum", "Product", "Dividend", "Percentage", "Belasting"])
        df_lijst.to_csv("Degiro - Dividend - Overzicht.csv", sep=";", index=False, decimal=",")
        df_dividend.to_csv("Degiro - Dividend - Totaal.csv", sep=";", index=False, decimal=",")
        df_betalingen.to_csv("Degiro - Dividend - Betalingen.csv", sep=";", index=False, decimal=",")

    def dividend_overview(self):
        self.get_dividends()
        self.dividend_verwerken()


if __name__ == "__main__":
    DegiroDividend().dividend_overview()

