import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime, date
import matplotlib.ticker as mtick


def make_stacked_value_plot(values_df:pd.DataFrame,
                            start_date=date(2000,1,1),
                            end_date=datetime.now().date(),
                            title=""):
    
    dates = values_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
    conditions = [date.date() >= start_date and date.date() <= end_date for date in dates]

    dates_selection = [date for date, condition in zip(dates, conditions) if condition]
    values_selection = values_df[conditions].drop('Datum', axis=1).dropna(axis=1, how="all").fillna(0)
    columns_selection = [column.split(" INC")[0].replace("CASH & CASH FUND & FTX ", "") for column in values_selection.columns]

    fig, ax = plt.subplots(figsize=(40, 15))
    plt.title(label=title)
    plt.stackplot(dates_selection, values_selection.T, labels=columns_selection)
    plt.legend(loc="upper center", ncols=4)
    plt.xlim(min(dates_selection), max(dates_selection))
    plt.ylim(0)
    plt.subplots_adjust(left=0.043, right=0.97, top=0.97, bottom=0.043)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: '€{:,.0f}'.format(x).replace(',', '.')))
    fig.savefig(f"{title}.png", format="png", dpi=200)


def make_plots(values_df:pd.DataFrame):
    make_stacked_value_plot(values_df, title="Portfolio waarde")

    dates = values_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)
    for year in range(min(dates).year, max(dates).year + 1):
        make_stacked_value_plot(values_df, date(year, 1, 1), date(year, 12, 31), f"Portfolio waarde {year}")


values_df = pd.read_csv(f"Degiro waarde.csv", sep=";", na_values=0) # decimal=","
make_plots(values_df)

