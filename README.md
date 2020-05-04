# Script for migrating owasp-modsecurity-crs repo

This script was developed to perform repository migration from the actual `SpiderLabs/owasp-modsecurity-crs` repo
to the new organization.

### Design decisions

Migrating repos is a complex task. Not everything can be migrated sometimes: original pull request branches are removed, etc.

The focus on this particular one was to:
- try to have a 1:1 mapping between the original issue number, and the new one.
- add links to original assets in the migrated one
- eliminate user mentions everywhere (they will send email to the user, so we need to be careful here)
- there are some numbers that don't have an origin issue (maybe deleted): what we do is just create a dummy destination issue.

## Testing

Tests were performed in the `crstest01/owasp-modsecurity-crs` test organization/repo. Full migration was performed.

When performing the migration tests, we hit the GitHub API limits around 300 issues migrated (API limits == 5000 per hour). So to migrate all our issues/prs (~ 1800), will take approximately 6 hours.


## The process

To migrate from one repository to the other, you need to:
- [x] create a new user for doing the migration. It is better to not be associated to a personal user. E.g. `CRS-migration-agent`.
- [x] generate a new token for the user, and export it using `GITHUB_TOKEN=<user token>`.
- create a new repository by importing the original repository.
  This will get all branches, tags to the new repo
- switch default branch to v3.3/dev in the destination repo
- execute this script

1. First time, call it using `--init` so milestones and labels get copied.
   Example: `./duplicate_repo.py --init --repo CoreRuleSet/crs --start 1 --end 300`

2. Get all issues and pull requests and create them in order in the new repo.
   Iterate over all the issues, 300 each time.
   `./duplicate_repo.py --repo CoreRuleSet/crs --start 301 --end 600`

## Migation day

The day set for the migration, the origin repository *must* be set to read-only first. That way, we guarantee that a migrated issue won't get additional comments. But the new repo still should not allow manual issue creation yet, so the order is preserved. Also, the migration should be to a private repo first, and then made public. This way we prevent writing in issues mid-migration.

## Full testing

[x] Full test was performed, you can see the results in the crstest01 organization.
