Stage all changes and commit with the provided message.

Run the following commands in sequence:
1. `git add -A` to stage all changes (new, modified, and deleted files)
2. `git commit -m "$ARGUMENTS"` to commit with the message provided by the user

If no message is provided in $ARGUMENTS, ask the user for a commit message before proceeding.

After committing, show the output of `git log --oneline -1` so the user can confirm the commit was created.
