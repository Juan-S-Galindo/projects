# Solution using lists instead of dictonary because why not....

import csv
import os

totalVotes = 0  # Empty variable to keep track of the vote tally
candidateVotes = []
candidatelist = []
winnerVotes = 0
winnerCandidate = 0

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
        candidateIndex = row[
            2
        ]  # Declares the variable candiadate  index as the value under the column with the names of the candidates.
        totalVotes += (
            1  # Adds 1 vote to the total tally every time we do a row iteration.
        )

        if (
            candidateIndex in candidatelist
        ):  # If the candidate's name is the list called candidatelist.
            candidateVotes[candidatelist.index(candidateIndex)] += (
                1  # Finds the index of the candidate in the candadidate list and returns the index to the candidate votes and adds 1 to the index.
            )

            if (
                candidateVotes[candidatelist.index(candidateIndex)] > winnerVotes
            ):  # Keeps track of the candidate with the most votes.
                winnerVotes = candidateVotes[
                    candidatelist.index(candidateIndex)
                ]  # Tracks the highest vote count.
                winnerCandidate = candidateIndex  # Tracks the winning candidate.

        else:  # If the name of the candidate is not in the list we append the name of the candidate and append 1 to the list of votes.
            candidatelist.append(candidateIndex)
            candidateVotes.append(1)

        if (
            totalVotes + 1 == csvTotalLines
        ):  # If the total number of votes +1 to account for the title of the file are the same as teh total csvlines.
            s = "-" * 20
            textCopy = open("textCopy.txt", "w")  # creates copy as TXT

            print(s, file=textCopy)
            print("ELECTION RESULTS", file=textCopy)
            print(s, file=textCopy)
            print(f"Total Votes: {totalVotes}", file=textCopy)
            print(s, file=textCopy)

            for i in range(
                len(candidatelist)
            ):  # for loop to print a line for each candidate.
                print(
                    f"{candidatelist[i]}: {(candidateVotes[i] / totalVotes) * 100:.3f}% ({candidateVotes[i]})",
                    file=textCopy,
                )  # Prints the key and the value in the key rounded to 2 decimals in % format and also prints the total votes AND SAVES THE TXT COPY.

            print(s, file=textCopy)
            print(
                f"Winner: {winnerCandidate}", file=textCopy
            )  # Prints the name of the candidate with the highest votes.
            print(s, file=textCopy)

            textCopy.close()  # Closes the txt file.

            # --------------------------------------------------------------------------------------------------------------
            print(s)  # Prints the results in the command line.
            print("ELECTION RESULTS")
            print(s)
            print(f"Total Votes: {totalVotes}")
            print(s)
            for i in range(
                len(candidatelist)
            ):  # for loop to print a line for each candidate.
                print(
                    f"{candidatelist[i]}: {(candidateVotes[i] / totalVotes) * 100:.3f}% ({candidateVotes[i]})"
                )

            print(s)
            print(f"Winner: {winnerCandidate}")
            print(s)
