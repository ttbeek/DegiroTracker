from io import StringIO
from pandas import read_csv
from datetime import datetime, timedelta
from pathlib import Path

from http.client import HTTPSConnection
from io import StringIO
from browser_cookie3 import chrome, firefox
from os import _exit
from pyuac import isUserAdmin, runAsAdmin
from csv import QUOTE_NONNUMERIC

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
        # cookie_jar = firefox(domain_name=BASE_URL)

        for cookie in cookie_jar:
            if cookie.name == "JSESSIONID":
                return cookie.value
        raise Exception("Geen verslagen kunnen ophalen. Controleer of je ingelogd bent op Degiro in Google Chrome!")


    def get_report(self, report, date=None):
        if report == "positionReport":
            # print(date.strftime("%d-%m-%Y"))
            day, month, year = datetime.strftime(date, "%d-%m-%Y").split("-")
            url = f"/portfolio-reports/secure/v3/{report}/csv?sessionId={self.session_id}&country=NL&lang=nl&toDate={day}/{month}/{year}"
        else:
            print(f"Ophalen '{report}'...")
            day, month, year = datetime.strftime(datetime.now(), "%d-%m-%Y").split("-")
            url = f"/portfolio-reports/secure/v3/{report}/csv?sessionId={self.session_id}&country=NL&lang=nl&fromDate=01/01/2000&toDate={day}/{month}/{year}"

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

