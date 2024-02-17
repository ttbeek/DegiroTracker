import pandas as pd
from datetime import datetime, timedelta


STORTING_TRANSACTIES = [
    "iDEAL storting",
    "Terugstorting",
    "Processed Flatex Withdrawal",
    "Reservation iDEAL / Sofort Deposit",
    "iDEAL Deposit",
    "Processed Flatex Withdrawal",
    "flatex terugstorting"]


class DegiroProcessor():
    def __init__(self) -> None:
        self.cash_report = pd.read_csv("data\\cash.csv", sep=";")
        self.transactions_report = pd.read_csv("data\\transactions.csv", sep=";")


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

        values_df = pd.DataFrame(columns=["Datum"])
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
                    value_report = pd.read_csv(f"data\\portfolio\\Portfolio {date_formatted}.csv", sep=";")
                except Exception as e:
                    date += timedelta(1)
                    print(e)
                    continue

                values_day = {}
                values_day["Datum"] = [date_formatted]

                for row in value_report.itertuples():
                    if row._6 != "0,00":
                        values_day[row.Product] = [row._6.replace(",", ".")]

                values_df = values_df.merge(pd.DataFrame.from_dict(values_day), how="outer")

                cash_total = sum([float(row["Waarde in EUR"].replace(",", ".")) for index, row in value_report.iterrows() if "CASH & CASH FUND & FTX CASH" in row["Product"]])


                value_total = sum([float(value.replace(",", ".")) for value in list(value_report["Waarde in EUR"])])
                result_total = value_total - deposited - costs
                result_percentage = result_total / (value_total - result_total) * 100
                daily_result_total = result_total - previous_result
                # daily_result_percentage = daily_result_total / (value_total - daily_result_total) * 100
                daily_result_percentage = daily_result_total / (value_total - daily_result_total - cash_total) * 100

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
                break

        stats_df = pd.DataFrame(data=stats, columns=["Datum", "Waarde", "Inleg", "Kosten", "Rendement", "Rendement(%)", "Dagelijks rendement", "Dagelijks rendement(%)"])
        for column in set(values_df.columns) - {"Datum"}:
            values_df[column] = pd.to_numeric(values_df[column], errors="coerce")
        
        values_df.to_csv("Degiro - Waarde.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Waarde' opgeslagen!")
        stats_df.to_csv("Degiro - Rendement.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Rendement' opgeslagen!\n")

