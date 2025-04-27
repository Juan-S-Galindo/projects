import csv
import os

candidatesDict = {}  # Empty dictionary to build our candidate tally
totalVotes = 0  # Empty variable to keep track of the vote tally
candidateList = []  # Empty list to  keep track of the candidates names.


def PyPoll(row):  # PyPoll function to print the final results and all the mumbo jumbo
    global totalVotes  # Calls global variables to use them inside the function.
    global candidatesDict
    global candidateList

    candidateIndex = row[
        2
    ]  # Declares the variable candiadate  index as the value under the column with the names of the candidates.
    totalVotes += 1  # Adds 1 vote to the total tally every time we do a row iteration.

    if (
        candidateIndex in candidatesDict
    ):  # If the candidate's name is in the keys of the  candidate global dictionary.
        candidatesDict[candidateIndex] += (
            1  # Adds 1 vote to the value of the key of the respective candidate.
        )

    else:  # If the name of the candidate is not in the dictionary
        candidatesDict.update(
            {candidateIndex: 1}
        )  # Takes the candidate global dictionary, creates a new key with the name of the candidate and sets the value to 1 to account for the first vote.

    keyMax = max(
        candidatesDict, key=candidatesDict.get
    )  # Variable to return the key with  the highest value.

    if (
        totalVotes + 1 == csvTotalLines
    ):  # if total votes + 1 to account for the header row is equal to the total lines in the csv print the results.
        s = "-" * 20
        textCopy = open("textCopy.txt", "w")  # creates copy as TXT

        print(s, file=textCopy)
        print("ELECTION RESULTS", file=textCopy)
        print(s, file=textCopy)
        print(f"Total Votes: {totalVotes}", file=textCopy)
        print(s, file=textCopy)

        def votes():  # Nested function to print the dictionary.
            for i in candidatesDict:  # for every index in the candidate dictionary.
                print(
                    (
                        f"{i}: {(candidatesDict[i] / totalVotes) * 100:.3f}% ({candidatesDict[i]})"
                    ),
                    file=textCopy,
                )  # Prints the key and the value in the key rounded to 2 decimals in % format and also prints the total votes AND SAVES THE TXT COPY.

        votes()  # Calls the nested function to print in the TXT file.

        print(s, file=textCopy)
        print(
            f"Winner: {keyMax}", file=textCopy
        )  # Prints the name of the candidate with the highest votes.
        print(s, file=textCopy)

        textCopy.close()  # Closes the txt file.
        # --------------------------------------------------------------------------------------------------------------
        print(s)  # Prints the results in the command line.
        print("ELECTION RESULTS")
        print(s)
        print(f"Total Votes: {totalVotes}")
        print(s)

        def votesT():  # Nested function to print the dictionary of the candidates.
            for i in candidatesDict:
                print(
                    f"{i}: {(candidatesDict[i] / totalVotes) * 100:.3f}% ({candidatesDict[i]})"
                )

        votesT()  # Calls the nested function to print in the TERMINAL.

        print(s)
        print(f"Winner: {keyMax}")
        print(s)


fileName = os.path.join(
    os.getcwd(),
    "projects/ut_data_viz_bootcamp/python/challenge_python/PyPoll/Resources/election_data.csv",
)  # Opens the CSV file.

with open(fileName, "r") as csvfile:  # Opens the file with reader settings as csvfile.
    csvreader = csv.reader(
        csvfile, delimiter=","
    )  # Csv reader  is assigned the csv file with delimiter: ,
    csvTotalLines = len(
        list(open(fileName))
    )  # Returns the total lines in the CSV file.
    csvheader = next(
        csvreader, None
    )  # Csvheader allows us to skip the header in the calculations.

    for row in csvreader:  # For every row in the csvreader
        PyPoll(row)  # Run the function for every row.
