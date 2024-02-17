import http.client
from io import StringIO
import pandas as pd
import browser_cookie3
from datetime import datetime, timedelta
import csv
import os
import pyuac

BASE_URL = "trader.degiro.nl"


class DegiroReciever():
    def __init__(self):
        if not os.path.exists("data"):
            os.mkdir("data")
        if not os.path.exists("data\\portfolio"):
            os.mkdir("data\\portfolio")


    def get_session(self):
        if not pyuac.isUserAdmin():
            try:
                pyuac.runAsAdmin(wait=False)
            except:
                raise Exception("Geen verslagen kunnen ophalen. Sta open het programma in 'admin' modus")
            os._exit(1)
        
        cookie_jar = browser_cookie3.chrome(domain_name=BASE_URL)
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

        conn = http.client.HTTPSConnection(BASE_URL)
        conn.request("GET", url, "", {})

        res = conn.getresponse()
        data = res.read().decode("utf-8")
        return data


    def reports_up_to_date(self):
        date_formatted = (datetime.now() - timedelta(1)).strftime("%d-%m-%Y")
        if os.path.exists(f"data\\portfolio\\Portfolio {date_formatted}.csv"):
            return True
        return False


    def save_portfolio_reports(self, date):
        print("Ophalen dagverslagen...\n")
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
        
        print("Ophalen verslagen...")
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

