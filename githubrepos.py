import requests
import time
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from requests.exceptions import RequestException

# GitHub API settings
GITHUB_API_BASE_URL = "https://api.github.com/search/repositories"
GITHUB_API_VERSION = "2022-11-28"

# Exponential backoff settings
MAX_RETRIES = 5  # Maximum retry attempts
BASE_BACKOFF_TIME = 5  # Initial backoff time in seconds

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


@dataclass
class RepoData:
    """Dataclass to store GitHub repository information."""
    name: str
    description: Optional[str]
    html_url: str
    stars: int
    forks: int


def search_github_repos(
    keywords: List[str], token: Optional[str] = None, min_stars: int = 0, min_forks: int = 0
) -> Dict[str, List[RepoData]]:
    """Search GitHub repositories based on keywords, applying rate limit handling and exponential backoff.

    Args:
        keywords (List[str]): List of search keywords.
        token (Optional[str]): GitHub API token for authentication (optional but recommended).
        min_stars (int): Minimum number of stars a repository should have.
        min_forks (int): Minimum number of forks a repository should have.

    Returns:
        Dict[str, List[RepoData]]: Dictionary mapping keywords to a list of repository data.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    repo_data = {}

    for keyword in keywords:
        params = {"q": keyword}
        try:
            all_repo_data_for_keyword = []
            next_page_url = GITHUB_API_BASE_URL
            retries = 0  # Retry counter

            while next_page_url:
                try:
                    logging.info(f"Searching for '{keyword}' at '{next_page_url}'")
                    response = requests.get(next_page_url, headers=headers, params=params)

                    # Handle rate limits
                    if response.status_code == 403:  # Forbidden (possibly due to rate limits)
                        remaining_limit = int(response.headers.get("X-RateLimit-Remaining", 1))
                        reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                        wait_time = max(reset_time - time.time(), 30)  # Ensure a minimum wait time
                        logging.warning(f"Rate limit exceeded. Waiting {wait_time:.0f} seconds...")
                        time.sleep(wait_time)
                        continue  # Retry the request

                    response.raise_for_status()
                    data = response.json()

                    # Extract relevant repo data
                    repo_data_for_keyword = []
                    for item in data.get("items", []):
                        if item["stargazers_count"] >= min_stars and item["forks_count"] >= min_forks:
                            repo_data_for_keyword.append(
                                RepoData(
                                    name=item["name"],
                                    description=item["description"],
                                    html_url=item["html_url"],
                                    stars=item["stargazers_count"],
                                    forks=item["forks_count"],
                                )
                            )

                    all_repo_data_for_keyword.extend(repo_data_for_keyword)

                    # Handle Pagination
                    if "Link" in response.headers:
                        link_header = response.headers["Link"]
                        next_links = [
                            link.split(";")[0].replace("<", "").replace(">", "").strip()
                            for link in link_header.split(",")
                            if 'rel="next"' in link
                        ]
                        next_page_url = next_links[0] if next_links else None
                    else:
                        next_page_url = None

                except RequestException as e:
                    if retries < MAX_RETRIES:
                        wait_time = BASE_BACKOFF_TIME * (2 ** retries)  # Exponential backoff
                        logging.warning(f"Request failed ({e}), retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        retries += 1
                    else:
                        logging.error(f"Max retries reached. Skipping '{keyword}'")
                        break  # Exit loop after max retries

            repo_data[keyword] = all_repo_data_for_keyword

        except RequestException as e:
            logging.error(f"Error searching for '{keyword}': {e}")
            repo_data[keyword] = []  # Ensure there's always an entry even with errors
            time.sleep(60)  # Fallback sleep in case of unexpected errors

    return repo_data


if __name__ == "__main__":
    # Example usage
    keywords = ["machine learning", "deep learning", "AI"]
    github_token = "your_personal_access_token_here"  # Replace with your GitHub API token

    results = search_github_repos(keywords, token=github_token, min_stars=100, min_forks=50)

    for keyword, repos in results.items():
        print(f"\nRepositories for '{keyword}':")
        for repo in repos:
            print(f"- {repo.name} ({repo.stars} ⭐, {repo.forks} forks) -> {repo.html_url}")
