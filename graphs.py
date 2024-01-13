import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
import numpy as np

def make_stacked_value_plot(values_df:pd.DataFrame):
    # values_df["date"] = datetime.strptime(values_df["Datum"], "%d-%m-%Y")
    dates = values_df.apply(lambda x: datetime.strptime(x["Datum"], "%d-%m-%Y"), axis=1)

    # values_df = pd.DataFrame(np.nan_to_num(values_df, nan=0), columns=values_df.columns)
    # print(values_df)
    # print(values_df["date"])
    # print(values_df["date"])datetime.strptime(values_df["Datum"], "%d-%m-%Y")
    # print([list(values_df[column].values) for column in values_df.columns if column == "Datum"])
    plt.stackplot(dates, values_df.drop('Datum', axis=1).T.fillna(0), labels=[column.split("INC")[0] for column in values_df.columns[1:]])
    plt.legend()
    plt.show()


values_df = pd.read_csv(f"Degiro waarde.csv", sep=";", decimal=",", na_values=0)
# print(values_df)
make_stacked_value_plot(values_df)
