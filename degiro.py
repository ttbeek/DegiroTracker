from reciever import DegiroReciever
from processor import DegiroProcessor
from transactions import DegiroTransactions
from dividend import DegiroDividend
from graphs import DegiroGraphs

if __name__ == "__main__":
    try:
        DegiroReciever().save_reports()
        DegiroProcessor().process_stats()
        DegiroTransactions().process_transactions()
        DegiroDividend().dividend_overview()
        DegiroGraphs().make_plots()
    except Exception as e:
        print("Error:", e)
    finally:
        input()

# pyinstaller --onefile --hidden-import='dividend.py' --hidden-import='graphs.py' --hidden-import='processor.py' --hidden-import='reciever.py' --hidden-import='ticker_data.py' --icon=pog.ico degiro.py
# pyinstaller --onefile --icon=pog.ico degiro.py