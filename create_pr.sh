#!/bin/bash
git checkout -b $1
echo "Created branch $1" > README.md
git commit -am "Created branch $1"
git push --set-upstream origin $1
gh pr create --title "Created branch $1" --body "Created branch $1" --base main --head $1
gh pr comment "$1" --body "Created branch $1"
#gh pr review $1 --comment -b "interesting"
gh pr merge "$1" --squash --delete-branch
git checkout main
git pull