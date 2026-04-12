Stage all changes and commit with an auto-generated summary of the staged changes.

Run the following commands in sequence:
1. `git add -A` to stage all changes (new, modified, and deleted files)
2. `git diff --cached` to inspect what is staged
3. Based on the staged diff, write a concise commit message that summarizes the actual changes (not a generic message). Use the summary as the commit message — do not ask the user for one unless $ARGUMENTS is provided, in which case use $ARGUMENTS as the commit message instead.
4. `git commit -m "<generated or provided message>"` to commit

After committing, show the output of `git log --oneline -1` so the user can confirm the commit was created.
