Update the title and body of the open PR for the current branch using the `gh` CLI.

Run the following steps in sequence:

1. Run `gh pr list --head $(git branch --show-current)` to find the PR number for the current branch. If no PR is found, tell the user and stop.
2. Run `gh pr view <number> --json files,commits,title,body` to retrieve the current PR details.
3. Read the changed files and commit messages from the JSON output to understand what was changed.
4. Based on the files and commits:
   - **Title**: Write a concise summary of all changes, no longer than 200 characters.
   - **Body**: Write a high-level markdown summary grouped by theme or area. Include a `## Summary` section with bullet points describing what changed and why (if inferable). Do not include a test plan unless $ARGUMENTS requests it.
5. Update the PR using:

```
gh pr edit <number> --title "<generated title>" --body "$(cat <<'EOF'
<generated body>
EOF
)"
```

After updating, print the PR URL so the user can open it.
