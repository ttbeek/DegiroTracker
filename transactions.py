from datetime import date, datetime, timedelta
from pandas import DataFrame, read_csv


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

