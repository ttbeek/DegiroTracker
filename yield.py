import pandas as pd
from dataclasses import dataclass
from datetime import date, datetime, timedelta


ADD_CASH = False

class DegiroYield():
    def __init__(self) -> None:
        # self.cash_report = pd.read_csv("data\\cash.csv", sep=";")
        # self.transactions_report = pd.read_csv("data\\transactions.csv", sep=";")
        self.value = self.set_date_index(pd.read_csv("Degiro - Waarde.csv", sep=";", decimal=","))
        self.profit = self.set_date_index(pd.read_csv("Degiro - Rendement.csv", sep=";", decimal=","))

    def set_date_index(self, dataframe:pd.DataFrame) -> pd.DataFrame:
        # dataframe["date"] = dataframe.apply(lambda x: pd.to_datetime(datetime.strptime(x["Datum"], "%d-%m-%Y").date()), axis=1)
        # dataframe.set_index("date", inplace=True)
        # return dataframe.drop("Datum", axis="columns")
        return dataframe.set_index("Datum")

    def get_start_date(self):
        cash_report_start = datetime.strptime(self.cash_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        transaction_report_start = datetime.strptime(self.transactions_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        return min(cash_report_start, transaction_report_start)
    
    def get_yield1(self):
        date = self.get_start_date()
        while date < datetime.now() - timedelta(1):
            pass
    
    def get_yield(self, start, end):
        tracked_value = 1

        date = start
        while date <= end:
            date_formatted = date.strftime("%d-%m-%Y")

            if date_formatted not in self.profit.index:
                break

            waarde = self.profit.loc[date_formatted]["Waarde"]
            change = self.profit.loc[date_formatted]["Dagelijks rendement"]
            cash = self.value.loc[date_formatted][["CASH & CASH FUND & FTX CASH (EUR)", "CASH & CASH FUND & FTX CASH (USD)"]].sum()

            profit = change / (waarde - change - cash)

            tracked_value = tracked_value * (1 + profit)


            date += timedelta(1)

        result = round(tracked_value * 100 - 100, 2)
        print(f"{start.year}: {result} %")
        return result


if __name__ == "__main__":
    degiro = DegiroYield()
    degiro.get_yield(date(2020, 1, 9), date(2020, 12, 31))
    degiro.get_yield(date(2021, 1, 1), date(2021, 12, 31))
    degiro.get_yield(date(2022, 1, 1), date(2022, 12, 31))
    degiro.get_yield(date(2023, 1, 1), date(2023, 12, 31))
    degiro.get_yield(date(2024, 1, 1), date(2024, 12, 31))
    degiro.get_yield(date(2025, 1, 1), date(2025, 12, 31))

    # degiro.get_yield(date(2020, 1, 9), date(2024, 2, 14))
    # degiro.get_yield(date(2023, 3, 22), date(2024, 3, 22))
    