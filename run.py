# import subprocess
import requests
import os
import json
import sys

ADDR = "https://cimetrics.io/"
CI_METRICS_HEADER = "### CI Metrics"
GITHUB_REPO_API = "https://api.github.com/repos/"


def login(public_key, private_key):
    print("Logging in")

    url = f"{ADDR}login"
    print(f"url: {url}")

    headers = {"Content-Type": "application/json"}
    print(f"headers: {headers}")

    payload = json.dumps(
        {
            "public_key": public_key,
            "private_key": private_key,
        }
    )
    print(f"payload: {payload}")

    response = requests.post(
        url=url,
        data=payload,
        headers=headers,
    )
    print(f"response: {response}")
    assert response.status_code == 200

    return response.cookies


# Uploads metrics
def upload(session_cookie, sha, public_key, private_key, data, repo):
    print("Running upload.")

    url = f"{ADDR}metrics"
    print(f"url: {url}")

    headers = {"Content-Type": "application/json"}
    print(f"headers: {headers}")

    payload = json.dumps(
        {
            "sha": sha,
            "repo": repo,
            "metrics": data,
        }
    )
    print(f"payload: {payload}")

    response = requests.post(
        url=url, data=payload, headers=headers, cookies=session_cookie
    )
    print(f"response: {response}")
    assert response.status_code == 200


# Gets metrics difference
def diff(session_cookie, base, head, public_key, private_key):
    print(f"Running diff.")

    url = f"{ADDR}commits"
    print(f"url: {url}")

    headers = {"Content-Type": "application/json"}
    print(f"headers: {headers}")

    payload = json.dumps(
        {
            "commits": [base, head],
        }
    )
    print(f"payload: {payload}")

    response = requests.post(
        url=url, data=payload, headers=headers, cookies=session_cookie
    )
    print(f"response: {response}")

    assert response.status_code == 200

    response_json = response.json()
    print(f"response_json: {response_json}")

    assert base in response_json
    assert head in response_json

    changes = {}
    commit_one = response_json[base]
    for key, value in commit_one.items():
        changes[key] = {"from": value, "to": None}

    commit_two = response_json[head]
    for key, value in commit_two.items():
        if key in changes:
            changes[key]["to"] = value
        else:
            changes[key] = {"from": None, "to": value}

    print(f"changes: {changes}")

    table_set = []
    for key, value in changes.items():
        x = value["from"]
        y = value["to"]
        if x != None and y != None:
            d = y - x
            pd = f"{100 * float(d) / float(x):+.2f}" if x != 0 else "NaN"
            table_set.append(
                (
                    key,
                    pd,
                    f"{d:+,}",
                    f"{x:,}",
                    f"{y:,}",
                )
            )
        else:
            table_set.append(
                (
                    key,
                    "NaN",
                    "NaN",
                    "None" if x is None else f"{x:,}",
                    "None" if y is None else f"{y:,}",
                )
            )
    print(f"table_set: {table_set}")

    # Sort diff by %
    def get_sort_key(x):
        if x[1] == "NaN":
            return float(-1)
        else:
            return abs(float(x[1]))

    table_set.sort(reverse=True, key=get_sort_key)

    print(f"table_set: {table_set}")

    table = "Metric|∆%|∆|Old|New\n---|--:|--:|--:|--:\n"
    for components in table_set:
        table += "|".join(components)
        table += "\n"

    return table


# Posts metrics difference on PRs
def post(repo, issue, token, table, base, head):
    print(f"Running post.")

    # Get list of comments
    url = f"{GITHUB_REPO_API}{repo}/issues/{issue}/comments"
    print(f"url: {url}")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    print(f"headers: {headers}")

    response = requests.get(
        url=url,
        headers=headers,
    )
    print(f"response: {response}")
    assert response.status_code == 200

    response_json = response.json()
    print(f"response_json: {response_json}")

    id = None
    for comment in response_json:
        if comment["body"].startswith(CI_METRICS_HEADER):
            id = comment["id"]
    print(f"id: {id}")

    payload = json.dumps(
        {
            "body": f"{CI_METRICS_HEADER}\n{table}\n🔍 View full report in CIMetrics at `https://cimetrics.io/{repo}/<your branch>/{base}/{head}`."
        }
    )

    # If CI metrics comment is not present, post it.
    if id == None:
        url = f"{GITHUB_REPO_API}{repo}/issues/{issue}/comments"
        print(f"url: {url}")

        response = requests.post(
            url=url,
            data=payload,
            headers=headers,
        )
        print(f"response: {response}")
        assert response.status_code == 201
    # Else if CI metrics comment present, update it.
    else:
        url = f"{GITHUB_REPO_API}{repo}/issues/comments/{id}"
        print(f"url: {url}")

        response = requests.patch(
            url=url,
            data=payload,
            headers=headers,
        )
        print(f"response: {response}")
        assert response.status_code == 200


print(f"os.environ: {os.environ}")

public_key = os.environ["PUBLIC_KEY"]
print(f"public_key: {public_key}")
private_key = os.environ["PRIVATE_KEY"]
print(f"private_key: {private_key}")
head = os.environ["HEAD"]
print(f"head: {head}")

DATA_TEXT = "DATA_TEXT"
DATA_FILE = "DATA_FILE"
REPO = "GITHUB_REPOSITORY"

data_text = os.environ.get(DATA_TEXT)
data_file = os.environ.get(DATA_FILE)
repo = os.environ[REPO]

session_cookie = login(public_key, private_key)
if data_text is None and data_file is not None:
    print(f"data_text: {data_file}")
    data_str = open(data_file, "r").read()
    print(f"data_str: {data_str}")
    upload(session_cookie, head, public_key, private_key, json.loads(data_str), repo)
elif data_text is not None and data_file is None:
    print(f"data_text: {data_text}")
    upload(session_cookie, head, public_key, private_key, json.loads(data_text), repo)
elif data_text is None and data_file is None and repo is None:
    print(f"Neither `{DATA_TEXT}`, `{DATA_FILE}` or `{REPO}` set, skipping upload.")
else:
    raise Exception(
        f"`{DATA_TEXT}` ({data_text}) and `{DATA_FILE}` ({data_file}) must not both be set."
    )

BASE = "BASE"
ISSUE = "ISSUE"
TOKEN = "TOKEN"

base = os.environ.get(BASE)
issue = os.environ.get(ISSUE)
token = os.environ.get(TOKEN)

if base is not None and issue is not None and token is not None and repo is not None:
    table = diff(session_cookie, base, head, public_key, private_key)
    post(repo, issue, token, table, base, head)
elif base is None and issue is None and token is None:
    print(f"None of `{BASE}`, `{ISSUE}` or `{TOKEN}` set, skipping diff.")
else:
    raise Exception(
        f"`{BASE}` ({base}), `{ISSUE}` ({issue}) and `{TOKEN}` ({token}) must all be set when any are set."
    )
