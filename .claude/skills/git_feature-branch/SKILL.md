Create a new Git feature branch in the format `feature/<reason-with-hyphens>`.

If $ARGUMENTS is provided, use it as the branch description.
If $ARGUMENTS is NOT provided, ask the user: "What is the purpose of this branch?" and wait for their answer before proceeding.

Once you have the description:
1. Convert it to lowercase, replace spaces and special characters with hyphens, and strip leading/trailing hyphens to form the slug.
2. Construct the branch name as `feature/<slug>`.
3. Run `git checkout -b <branch-name>` to create and switch to the branch.
4. Confirm the branch was created by showing the output of `git branch --show-current`.
