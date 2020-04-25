#!/usr/bin/env python3

"""
Script for migrating owasp-modsecurity-crs repo
"""
from github import Github
from github.GithubException import UnknownObjectException, GithubException
import os
import sys
import re
import argparse


def copy_milestones(source, destination):
    """
    Copy milestones to destination.

    Seems like milestones in the original repo don't have the first (1), so they being from 2.
    This is not a problem itself, but we need to check the name of the milestone before
    assigning it to thedestonation repository.
    """
    milestones = source.get_milestones(state="all")

    for milestone in milestones:
        # milestones need due date
        try:
            destination.create_milestone(
                title=milestone.title,
                state=milestone.state,
                description=milestone.description,
            )
            print("* Migrated milestone {m}".format(m=milestone.title))
        except GithubException:
            if args.verbose:
                print("Milestone {m} already exists in repo".format(m=milestone.title))


def copy_labels(source, destination):
    """
    Copies labels to destination repo.

    This can be executed without problems.

    """
    labels = source.get_labels()
    if args.verbose:
        print("Cloning labels")

    for label in labels:
        try:
            if label.description is None:
                description = ""
            else:
                description = label.description
            destination.create_label(
                name=label.name, color=label.color, description=description
            )
            print("> Migrated label: {name}".format(name=label.name))
        except GithubException:
            if args.verbose:
                print("Label {label} already exists in repo".format(label=label.name))


def migrate_issue(orig_issue, destination, dest_milestones, dest_labels):
    """
    Migrates issue to destination depo.

    Tries to remove mentions to all users in the body and comments.
    """

    body = """_Issue originally created by user {user} on date {date}.
            Link to original issue: {link}._\n\n""".format(
                user=orig_issue.user.login, date=orig_issue.created_at,
                link=orig_issue.html_url
            )

    body += re.sub(OPERATORS_RE, r'**\1**', orig_issue.body)

    issue_args = {"title": orig_issue.title, "body": body}

    # Not adding assignees: this will @ lots of people!
    # if orig_issue.assignees is not None:
    #    issue_args['assignees'] = orig_issue.assignees

    if orig_issue.milestone is not None:
        # We need to find the milestone in this repo, as we will
        # have differences (SpiderLabs begins at #3)
        for m in dest_milestones:
            if m.title == orig_issue.milestone.title:
                issue_args["milestone"] = m
                break

    if orig_issue.labels is not None:
        issue_args["labels"] = orig_issue.labels

    new_issue = destination.create_issue(**issue_args)

    print(">> Migrating issue #{n} as new #{new_n}".format(
        n=orig_issue.number, new_n=new_issue.number))

    # now add the original body
    for comment in orig_issue.get_comments():
        comment_body = """_User {user} commented on date {date}:_\n\n""".format(
            user=comment.user.login, date=comment.created_at
        )

        comment_body += re.sub(OPERATORS_RE, r'**\1**', comment.body)

        new_comment = new_issue.create_comment(body=comment_body)
        for reaction in comment.get_reactions():
            new_comment.create_reaction(reaction.content)
    print(">>> Changing issue state to {state}".format(state=orig_issue.state))

    new_issue.edit(state=orig_issue.state)


def migrate_pr(orig_pull, destination, milestones, labels):
    """
    Migrate original PR.

    This is tricky because PR source repos may have dissaperead, therefore PR
    creation will fail. I've decided to create them as issues so we keep the
    numbering.
    """

    body = """_Issue for tracking original pull request created by user {user} on date {date}.
            Link to original PR: {link}._\n\n""".format(
                user=orig_pull.user.login, date=orig_pull.created_at,
                link=orig_pull.html_url
            )

    if orig_pull.head is not None:
        body += "HEAD is: {sha}\n".format(sha=orig_pull.head.sha)

    if orig_pull.base is not None:
        body += "BASE is: {sha}\n".format(sha=orig_pull.base.sha)

    body += re.sub(OPERATORS_RE, r'**\1**', orig_pull.body)

    pr_args = {
        "title": orig_pull.title,
        "body": body,
    }

    new_pr = destination.create_issue(**pr_args)

    print(">> Migrating pullreq #{n} as new issue #{new_n}".format(
        n=orig_pull.number, new_n=new_pr.number))

    # now add the original review comments
    for comment in orig_pull.get_comments():
        comment_body = """_User {user} commented on date {date}:_\n\n""".format(
            user=comment.user.login, date=comment.created_at
        )

        comment_body += re.sub(OPERATORS_RE, r'**\1**', comment.body)
        new_comment = new_pr.create_comment(body=comment_body)
        for reaction in comment.get_reactions():
            new_comment.create_reaction(reaction.content)

    new_pr.edit(state=orig_pull.state)


def get_all_pulls(repo):
    """ Get all pull requests from repo """
    pulls = repo.get_pulls(state="all", sort="created")

    return pulls


def get_all_issues(repo):
    """ Get all issues from repo """
    issues = repo.get_issues(state="all", sort="created")

    return issues


def get_contributors(repo):
    """ Get all contributors """
    contributors = repo.get_stats_contributors()

    authors = [c.author.login for c in contributors]

    return authors


def get_everything(repo):
    """ Gets everything """
    all_issues = get_all_issues(repo)
    all_prs = get_all_pulls(repo)

    # Now we need to merge both based on numbering

    all_repo = all_issues + all_prs

    all_repo.sort(key=lambda x: x.number, reverse=True)

    for item in all_repo:
        print(item)


description = """
To migrate from one repository to the other, you need to:
- create a new repository by importing the original repository.
  This will get all branches, tags to the new repo
- switch default branch to v3.3/dev in the destination repo
- execute this script

1) First time, call it using `--init` so milestones and labels get copied.
2) Get all issues and pull requests and create them in order in the new repo.
As the limit for the Github API is 5000 requests per hour, you will hit it at
approximately 300 issues migrated.
"""

# MAIN

parser = argparse.ArgumentParser(description=description)
parser.add_argument("--start", help="start migrating from given issue number",
                    type=int)
parser.add_argument("--end", help="migrate until this issue number",
                    type=int)
parser.add_argument("--verbose", help="increase output verbosity",
                    action="store_true")
parser.add_argument("--initial", help="migrate labels and milestones (execute once)",
                    action="store_true")
parser.add_argument("--repo", help="destination repo to use. MUST exist beforehand!",
                    type=str)
args = parser.parse_args()


GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', None)
# or using an access token
if GITHUB_TOKEN is None:
    print("Please export your github token using the GITHUB_TOKEN env var")
    sys.exit()

g = Github(GITHUB_TOKEN)

ORIGINAL_REPO_NAME = "SpiderLabs/owasp-modsecurity-crs"
if args.repo:
    DESTINATION_REPO_NAME = args.repo
else:
    DESTINATION_REPO_NAME = "crstest01/owasp-modsecurity-crs"

orig = g.get_repo(ORIGINAL_REPO_NAME)
dest = g.get_repo(DESTINATION_REPO_NAME)

if args.initial:
    copy_milestones(orig, dest)
    copy_labels(orig, dest)

# Save a global copy of milestones
milestones = dest.get_milestones(state="all")
# Save a global copy of labels
labels = dest.get_labels()

OPERATORS_RE = r'@(?!:beginsWith|contains|containsWord|detectSQLi|detectXSS|endsWith|fuzzyHash|eq|ge|geoLookup|gsbLookup|gt|inspectFile|ipMatch|ipMatchF|ipMatchFromFile|ipmatchfromfile|le|lt|noMatch|pmf|pmFromFile|pm|rbl|rsub|rx|streq|strmatch|unconditionalMatch|validateByteRange|validateDTD|validateHash|validateSchema|validateUrlEncoding|validateUtf8Encoding|verifyCC|verifyCPF|verifySSN|within|rx)([a-zA-Z0-9]+)'

for n in range(args.start, args.end+1):
    limit = g.get_rate_limit()
    if limit.core.remaining < 50:
        print(f"Stopping the migration here, please start from {n} next time")
        sys.exit()

    print("+ Migrating #{number}".format(number=n))
    try:
        pull = orig.get_pull(n)
        migrate_pr(pull, dest, milestones, labels)
    except UnknownObjectException:
        try:
            issue = orig.get_issue(number=n)
            migrate_issue(issue, dest, milestones, labels)
        except Exception as e:
            print(e)
