import http.client
from io import StringIO
import pandas as pd
import browser_cookie3
from datetime import datetime, date, timedelta
import csv
import os
import pyuac
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
import numpy as np
import math
import seaborn as sns


SMALL_FONT_SIZE = 14
MEDIUM_FONT_SIZE = 20
BIGGER_FONT_SIZE = 30

NUMBER_OF_BINS = 100
BASE_URL = "trader.degiro.nl"
STORTING_TRANSACTIES = [
    "iDEAL storting",
    "Terugstorting",
    "Processed Flatex Withdrawal",
    "Reservation iDEAL / Sofort Deposit",
    "iDEAL Deposit",
    "Processed Flatex Withdrawal",
    "flatex terugstorting"]

plt.style.use('seaborn-v0_8')
plt.rc('font', size=SMALL_FONT_SIZE)          # controls default text sizes
plt.rc('axes', titlesize=MEDIUM_FONT_SIZE)     # fontsize of the axes title
plt.rc('axes', labelsize=MEDIUM_FONT_SIZE)    # fontsize of the x and y labels
plt.rc('xtick', labelsize=SMALL_FONT_SIZE)    # fontsize of the tick labels
plt.rc('ytick', labelsize=SMALL_FONT_SIZE)    # fontsize of the tick labels
plt.rc('legend', fontsize=MEDIUM_FONT_SIZE)   # legend fontsize
plt.rc('figure', titlesize=BIGGER_FONT_SIZE)  # fontsize of the figure title


def process_column_name(column:str):
    def remove_end(name:str, end:list[str]):
        for i in end:
            name = name.rsplit(maxsplit=1)[0] if name.rsplit(maxsplit=1)[-1] == i else name
        return name
    
    column = column.replace("-", "").strip().replace("CASH & CASH FUND & FTX ", "")
    column = "".join(column.split(" INC")[:-1] or column)
    return remove_end(column, ["LTD", "C", "IN"])


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
                # print(date_formatted)

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

        stats_df = pd.DataFrame(data=stats, columns=["Datum", "Waarde", "Inleg", "Kosten", "Rendement", "Rendement(%)", "Dagelijks rendement", "Dagelijks rendement(%)"])
        for column in set(values_df.columns) - {"Datum"}:
            values_df[column] = pd.to_numeric(values_df[column], errors="coerce")
        
        values_df.to_csv("Degiro - Waarde.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Waarde' opgeslagen!")
        stats_df.to_csv("Degiro - Rendement.csv", sep=";", index=False, decimal=",")
        print("Verslag 'Degiro - Rendement' opgeslagen!\n")


class DegiroGraphs():
    def __init__(self):
        if not os.path.exists("graphs"):
            os.mkdir("graphs")


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
        col = sns.color_palette("gist_rainbow", len(values_selection.columns))
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
        min_bin = math.floor(min(data) / binsize) * binsize
        max_bin = math.ceil(max(data) / binsize) * binsize

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
        ax.locator_params(axis='x', nbins=15) 
        ax.set_xlim(min(bins), max(bins))

        if kolom == "Dagelijks rendement":
            ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '€{:,.0f}'.format(c).replace(',', '.')))
        elif kolom == "Dagelijks rendement(%)":
            ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda c, _: '{:,.0f}%'.format(c).replace(',', '.')))

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
        if not Path(f"Degiro - Waarde.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro waarde.csv' bestaat.")
        if not Path(f"Degiro - Rendement.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro winst.csv' bestaat.")
        
        self.values_df = pd.read_csv(f"Degiro - Waarde.csv", sep=";", na_values=0, decimal=",")
        self.stats_df = pd.read_csv(f"Degiro - Rendement.csv", sep=";", na_values=0, decimal=",")
        
        self.make_profit_plot(Path("graphs\\Portfolio - Rendement.png"))
        self.make_stacked_value_plot(Path("graphs\\Portfolio - Waarde.png"))
        self.make_scatterplot_daily_change(Path("graphs\\Veranderingen - Verhouding.png"))
        self.make_histogram_plot(Path("graphs\\Veranderingen - Procentueel.png"), "Dagelijks rendement(%)")
        self.make_histogram_plot(Path("graphs\\Veranderingen - Waarde.png"), "Dagelijks rendement")

        dates = self.values_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
        for year in range(min(dates).year, max(dates).year + 1):
            if not os.path.exists(f"{year}"):
                os.mkdir(f"graphs\\{year}")
            
            self.make_profit_plot(
                Path(f"graphs\\{year}\\Portfolio - Rendement {year}.png"),
                date(year, 1, 1),
                date(year, 12, 31))
            self.make_stacked_value_plot(
                Path(f"graphs\\{year}\\Portfolio - Waarde {year}.png"),
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
        print("Alle grafieken zijn opgeslagen!")
        print("Dit venster kan gesloten worden")


if __name__ == "__main__":
    try:
        DegiroReciever().save_reports()
        DegiroProcessor().process_stats()
        DegiroGraphs().make_plots()
    except Exception as e:
        print("Error:", e)
    finally:
        input()

# pyinstaller --onefile --icon=pog.ico degiro.py