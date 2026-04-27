Create a new Git feature branch in the format `feature/<reason-with-hyphens>`.

If $ARGUMENTS is provided, use it as the branch description.
If $ARGUMENTS is NOT provided, ask the user: "What is the purpose of this branch?" and wait for their answer before proceeding.

Once you have the description:
1. Convert it to lowercase, replace spaces and special characters with hyphens, and strip leading/trailing hyphens to form the slug.
2. Construct the branch name as `feature/<slug>`.
3. Switch to the main branch: `git checkout main`.
4. Pull the latest changes: `git pull`.
5. Create and switch to the new branch: `git checkout -b <branch-name>`.
6. Confirm the branch was created by showing the output of `git branch --show-current`.
