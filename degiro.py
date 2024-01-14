import http.client
from io import StringIO
import pandas as pd
import browser_cookie3
from datetime import datetime, timedelta
import csv
import os
import pyuac


BASE_URL = "trader.degiro.nl"
STORTING_TRANSACTIES = [
    "iDEAL storting",
    "Terugstorting",
    "Processed Flatex Withdrawal",
    "Reservation iDEAL / Sofort Deposit",
    "iDEAL Deposit",
    "Processed Flatex Withdrawal",
    "flatex terugstorting"
]

class DegiroReciever():
    def __init__(self):
        if not os.path.exists("data"):
            os.mkdir("data")
        if not os.path.exists("data\\portfolio"):
            os.mkdir("data\\portfolio")


    def get_session(self):
        if not pyuac.isUserAdmin():
            print("launching as admin")
            pyuac.runAsAdmin()
            quit()

        cookie_jar = browser_cookie3.chrome(domain_name=BASE_URL)
        for cookie in cookie_jar:
            if cookie.name == "JSESSIONID":
                return cookie.value
        raise Exception("No session found")


    def get_report(self, report, date=None):
        if report == "positionReport":
            print(date.strftime("%d-%m-%Y"))
            day, month, year = datetime.strftime(date, "%d-%m-%Y").split("-")
            url = f"/reporting/secure/v3/{report}/csv?sessionId={self.session_id}&country=NL&lang=nl&toDate={day}/{month}/{year}"
        else:
            print(f"Fetching {report}")
            day, month, year = datetime.strftime(datetime.now(), "%d-%m-%Y").split("-")
            url = f"/reporting/secure/v3/{report}/csv?sessionId={self.session_id}&country=NL&lang=nl&fromDate=01/01/2000&toDate={day}/{month}/{year}"

        conn = http.client.HTTPSConnection(BASE_URL)
        conn.request("GET", url, "", {})

        res = conn.getresponse()
        data = res.read().decode("utf-8")
        return data


    def reports_up_to_date(self):
        date_formatted = datetime.now().strftime("%d-%m-%Y")
        if os.path.exists(f"data\\portfolio\\Portfolio {date_formatted}.csv"):
            return True
        return False


    def save_portfolio_reports(self, date):
        while date < datetime.now() - timedelta(1):
            date_string = datetime.strftime(date, "%d-%m-%Y")
            if not os.path.exists(f"data\\portfolio\\Portfolio {date_string}.csv"):
                data = self.get_report("positionReport", date)
                portfolio_report = pd.read_csv(StringIO(data), sep=",")  
                portfolio_report.to_csv(f"data\\portfolio\\Portfolio {date_string}.csv", sep=";", index=False, quoting=csv.QUOTE_NONNUMERIC)

            date += timedelta(1)


    def save_reports(self):
        if self.reports_up_to_date():
            return
        
        self.session_id = self.get_session()
        # Transaction report
        data = self.get_report("transactionReport")
        report = pd.read_csv(StringIO(data), sep=",")
        report.to_csv(f"data\\transactions.csv", sep=";", index=False, quoting=csv.QUOTE_NONNUMERIC)

        # Cash report
        data = self.get_report("cashAccountReport")
        report = pd.read_csv(StringIO(data), sep=",")  
        report.to_csv(f"data\\cash.csv", sep=";", index=False, quoting=csv.QUOTE_NONNUMERIC)

        # Portfolio reports
        self.save_portfolio_reports(self.get_start_date())


    def get_start_date(self):
        cash_report = pd.read_csv("data\\cash.csv", sep=";")
        transactions_report = pd.read_csv("data\\transactions.csv", sep=";")
        cash_report_start = datetime.strptime(cash_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        transaction_report_start = datetime.strptime(transactions_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        return min(cash_report_start, transaction_report_start)


class DegiroProcessor():
    def __init__(self) -> None:
        self.cash_report = pd.read_csv("data\\cash.csv", sep=";")
        self.transactions_report = pd.read_csv("data\\transactions.csv", sep=";")


    def get_start_date(self):
        cash_report_start = datetime.strptime(self.cash_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        transaction_report_start = datetime.strptime(self.transactions_report.tail(1).iloc[0]["Datum"], "%d-%m-%Y")
        return min(cash_report_start, transaction_report_start)


    def process_stats(self):
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
                print(date_formatted)

                cash_transactions = self.cash_report[self.cash_report["Datum"] == date_formatted]
                for cash_transaction in cash_transactions.itertuples():
                    if "transactiekosten" in cash_transaction.Omschrijving.lower():
                        costs += cash_transaction._9

                    elif any(deposit_transaction in cash_transaction.Omschrijving for deposit_transaction in STORTING_TRANSACTIES):
                        deposited += cash_transaction._9

                value_report = pd.read_csv(f"data\\portfolio\\Portfolio {date_formatted}.csv", sep=";")

                if date.weekday() <= 4:
                    values_day = {}
                    values_day["Datum"] = [date_formatted]

                    for row in value_report.itertuples():
                        if row._6 != "0,00":
                            values_day[row.Product] = [row._6.replace(",", ".")]

                    values_df = values_df.merge(pd.DataFrame.from_dict(values_day), how="outer")

                value_total = sum([float(value.replace(",", ".")) for value in list(value_report["Waarde in EUR"])])
                result_total = value_total - deposited - costs
                result_percentage = result_total / (value_total - result_total) * 100
                daily_result_total = result_total - previous_result
                daily_result_percentage = daily_result_total / (value_total - daily_result_total) * 100

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

        values_df.to_csv("Degiro waarde.csv", sep=";", index=False)
        stats_df = pd.DataFrame(data=stats, columns=["Datum", "Waarde", "Inleg", "Kosten", "Rendement", "Rendement(%)", "Dagelijks rendement", "Dagelijks rendement(%)"])
        stats_df.to_csv("Degiro winst.csv", sep=";", index=False)


    # def make_plot():
    #     data = 
        


if __name__ == "__main__":
    # reciever = DegiroReciever()
    # reciever.save_reports()

    processor = DegiroProcessor()
    processor.process_stats()

