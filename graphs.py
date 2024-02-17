import pandas as pd
from datetime import datetime, date
import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from pathlib import Path
import numpy as np
import math
import seaborn as sns

from ticker_data import get_ticker_data

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
        if not os.path.exists("graphs"):
            os.mkdir("graphs")
        
        self.values_df = pd.read_csv(f"Degiro - Waarde.csv", sep=";", na_values=0, decimal=",")
        self.stats_df = pd.read_csv(f"Degiro - Rendement.csv", sep=";", decimal=",")

        if not Path(f"Degiro - Waarde.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro waarde.csv' bestaat.")
        if not Path(f"Degiro - Rendement.csv").exists():
            raise Exception("Er is geen data bekend. Controleer of 'Degiro winst.csv' bestaat.")


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
        # ax.locator_params(axis='x', nbins=15) 
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
            ticker_data = pd.DataFrame(data={"Datum": []}|{ticker: [] for ticker in tickers.values()})

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
            if not os.path.exists(f"graphs\\{year}"):
                os.mkdir(f"graphs\\{year}")
            
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
        print("Alle grafieken zijn opgeslagen!")
        print("Dit venster kan gesloten worden")


if __name__ == "__main__":
    DegiroGraphs().make_plots()


