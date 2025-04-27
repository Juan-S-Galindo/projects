# Import what we need.
import csv
import os

totalMonths = 0  # Variables to keep track of the totals, min and max.
maxIncrease = 0
maxDecrease = 0
indexMonthMax = 0
indexMonthMin = 0
totalIncome = 0
netIncomeTotal = 0
priorMonthProfitLoss = 0


def PyBank(row):  # Defines the function
    global totalMonths  # Using global we can call the variables from outside the scope of the function.
    global maxIncrease
    global maxDecrease
    global indexMonthMax
    global indexMonthMin
    global totalIncome
    global netIncomeTotal
    global priorMonthProfitLoss

    dateIndex = row[
        0
    ]  # Declares the variable dateIndex as the value under the datae column.
    profitLossValue = int(
        row[1]
    )  # Declares the variable as the integer of the value under the gross profit loss column.

    totalMonths += 1  # Adds 1  to the total month counter everytime a row is iterated.
    totalIncome += profitLossValue  # Adds the the value of the gross profit/loss column to the total income everytime a row is iterated.

    def avgNetIncome():  # Nested function to calculate average income.
        avgPL = (
            netIncomeTotal / (totalMonths - 1)
        )  # Calulates average montly profit/loss  from the net income total by month and divides it by the total of the months - 1 to account for the first value.

        return avgPL

    if (
        totalMonths > 1
    ):  # During the first iteration the total months = 0 in this way the netIncome calculation starts after the first month.
        netIncome = (
            profitLossValue - priorMonthProfitLoss
        )  # Net income from the  current row P/L minus the prior month P/L
        netIncomeTotal += netIncome  # Keeps tally of the total net income

        if (
            netIncome > maxIncrease
        ):  # Conditional test to add max/min and to return the month of each.
            maxIncrease = netIncome
            indexMonthMax = dateIndex

        elif netIncome < maxDecrease:
            maxDecrease = netIncome
            indexMonthMin = dateIndex

        priorMonthProfitLoss = profitLossValue  # assigns the current P/L value to the prior month at the end of the iteration.

        s = "-" * 50
        return f"{s}\n Financial Analysis \n \n Total Months: {totalMonths} \n Net Income: ${totalIncome} \n Average Change: ${round(avgNetIncome(), 2)} \n Greatest Increase in Profits: {indexMonthMax} ({maxIncrease}) \n Greatest Decrease in Profits: {indexMonthMin} ({maxDecrease}) \n {s}"
        # ------>Returns the result of everything <-------------
    else:
        priorMonthProfitLoss += profitLossValue  # Assigns the first profit/loss value to the prior month profitLoss.


fileName = os.path.join(
    os.getcwd(),
    "projects/ut_data_viz_bootcamp/python/challenge_python/PyBank/Resources/budget_data.csv",
)  # Path to file

with open(fileName, "r") as csvfile:  # Opens the file with reader settings as csvfile.
    csvreader = csv.reader(
        csvfile, delimiter=","
    )  # Csv reader  is assigned the csv file with delimiter: ,
    csvheader = next(
        csvreader, None
    )  # to skip the header in the calculations. --> we would get error when adding the netIncome if we do not add this part.

    for row in csvreader:  # for every row in the csvreader
        results = PyBank(
            row
        )  # We run the PyBank function to every row and result is assguned to the variable results to print all the results  at the end.

print(results)  # print results.

textCopy = open("textCopy.txt", "w")  # Ceates copy as TXT
print(results, file=textCopy)
textCopy.close()
