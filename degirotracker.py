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

# pyinstaller --onefile --icon=DegiroTracker.ico --name=DegiroTracker degirotracker.py