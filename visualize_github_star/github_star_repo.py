import requests
import json
import csv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
HEADERS = {"Authorization": f"token {TOKEN}"}
PER_PAGE = 100
TIMEOUT = 10
MAX_RETRIES = 3


def setup_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_all_starred(session):
    page = 1
    repos = []
    with tqdm(desc="📥 Fetching pages", unit="page", leave=False) as pbar:
        while True:
            url = f"https://api.github.com/users/Yrd980/starred?per_page={PER_PAGE}&page={page}"
            try:
                response = session.get(url, headers=HEADERS, timeout=TIMEOUT)
                response.raise_for_status()
                data = response.json()

                if not data:
                    break

                repos.extend(data)
                pbar.set_postfix({"repos": len(repos)})
                pbar.update(1)
                page += 1

            except Exception as e:
                print(f"\n⚠️ Error on page {page}: {str(e)}")
                break
    return repos


def save_data(repos):
    with open("starred_repos.json", "w") as f:
        json.dump(repos, f, indent=2)

    with open("starred_repos.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "URL", "Description", "Language", "Stars", "Archived"])

        for repo in tqdm(repos, desc="💾 Saving CSV", unit="repo"):
            writer.writerow(
                [
                    repo["full_name"],
                    repo["html_url"],
                    repo["description"] or "",
                    repo["language"] or "N/A",
                    repo["stargazers_count"],
                    repo["archived"],
                ]
            )


if __name__ == "__main__":
    print("🚀 Starting GitHub Starred Repos Export")

    session = setup_session()

    print("⏳ Downloading repository data...")
    repositories = fetch_all_starred(session)

    print(f"\n✅ Downloaded {len(repositories)} repositories")
    save_data(repositories)

    print("\n🎉 Export completed!")
    print(f"📂 JSON file: starred_repos.json")
    print(f"📊 CSV file: starred_repos.csv")
