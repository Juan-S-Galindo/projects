Create a draft pull request on GitHub using the `gh` CLI.

Run the following steps in sequence:

1. Run `git log origin/HEAD..HEAD --oneline` to get all local commits not yet pushed to remote.
2. Run `git diff origin/HEAD..HEAD` to get the full diff of all unpushed changes.
3. Based on the commit list and diff:
   - **Title**: Write a concise summary of all changes, no longer than 250 characters.
   - **Body**: Write a high-level markdown summary of all changes grouped by theme or area. Include a "## Summary" section with bullet points. Do not include a test plan unless $ARGUMENTS requests it.
4. Create the PR in draft mode using:

```
gh pr create --draft --title "<generated title>" --body "$(cat <<'EOF'
<generated body>
EOF
)"
```

After creation, print the PR URL so the user can open it.
