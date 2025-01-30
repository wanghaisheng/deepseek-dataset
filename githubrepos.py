import requests
import json
import time
import os
import logging
import argparse
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# GitHub API URL
GITHUB_API_URL = "https://api.github.com/search/repositories"

# Get GitHub Token from Environment Variable
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    logging.error("GitHub Token not found! Set it using 'export GITHUB_TOKEN=your_token'")
    exit(1)

# Common technologies and categories
TECH_STACKS = ["react", "nextjs", "vue", "angular", "django", "flask", "fastapi", "spring", "laravel", "express", "nodejs", "rails", "golang", "rust", "flutter"]
CATEGORIES = {
    "ecommerce": ["shop", "store", "ecommerce", "cart", "shopify"],
    "game": ["game", "gaming", "unity", "unreal", "godot"],
    "ai": ["ai", "ml", "deep learning", "neural network", "chatbot"],
    "saas": ["saas", "subscription", "platform", "cloud"],
    "devtools": ["framework", "cli", "sdk", "api", "devtools"],
    "social": ["social", "chat", "messenger", "forum", "community"]
}

def search_github_repositories(query, min_stars=0, min_forks=0, per_page=50):
    """Fetch repositories from GitHub API."""
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    
    repos = []
    while True:
        response = requests.get(GITHUB_API_URL, headers=headers, params=params)
        if response.status_code == 403:
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time())) - time.time()
            logging.warning(f"Rate limit exceeded. Sleeping for {reset_time:.0f} seconds...")
            time.sleep(reset_time + 1)
            continue

        if response.status_code != 200:
            logging.error(f"GitHub API error {response.status_code}: {response.text}")
            break

        data = response.json()
        repos.extend(data.get("items", []))
        
        # Pagination Handling
        if "next" in response.links:
            GITHUB_API_URL = response.links["next"]["url"]
        else:
            break

        logging.info(f"Fetched {len(repos)} repositories so far...")
    
    return repos

def extract_keywords(description):
    """Extracts potential keywords from the description."""
    return list(set(re.findall(r"\b[a-zA-Z0-9\-]+\b", description.lower()))) if description else []

def categorize_repository(description):
    """Categorizes repositories based on keywords."""
    if description:
        for category, keywords in CATEGORIES.items():
            if any(keyword in description.lower() for keyword in keywords):
                return category
    return "other"

def extract_tech_stack(description):
    """Identifies technologies used in the repository."""
    return [tech for tech in TECH_STACKS if tech in description.lower()] if description else []

def process_repositories(repositories, min_stars, min_forks):
    """Processes repositories by filtering, extracting metadata, and categorizing."""
    return [
        {
            "name": repo["name"],
            "url": repo["html_url"],
            "description": repo["description"],
            "stars": repo["stargazers_count"],
            "forks": repo["forks_count"],
            "language": repo.get("language", "Unknown"),
            "tech_stack": extract_tech_stack(repo["description"]),
            "keywords": extract_keywords(repo["description"]),
            "category": categorize_repository(repo["description"]),
        }
        for repo in repositories
        if repo["stargazers_count"] >= min_stars and repo["forks_count"] >= min_forks
    ]

def save_to_json(data, output_filepath):
    """Saves repository data to a JSON file."""
    existing_data = []
    if os.path.exists(output_filepath):
        with open(output_filepath, "r", encoding="utf-8") as file:
            existing_data = json.load(file)

    # Merge and avoid duplicates
    urls = {repo["url"] for repo in existing_data}
    all_data = existing_data + [repo for repo in data if repo["url"] not in urls]
    
    with open(output_filepath, "w", encoding="utf-8") as file:
        json.dump(all_data, file, indent=4, ensure_ascii=False)
    
    logging.info(f"Results saved to: {output_filepath}")

def main():
    parser = argparse.ArgumentParser(description="Fetch and process GitHub repositories.")
    parser.add_argument("--keywords", required=True, help="Comma-separated search keywords")
    parser.add_argument("--min-stars", type=int, default=0, help="Minimum stars required")
    parser.add_argument("--min-forks", type=int, default=0, help="Minimum forks required")
    parser.add_argument("--output", default="github_repos.json", help="Output JSON file")
    args = parser.parse_args()
    
    search_query = " OR ".join(f"{term.strip()} in:name,description,readme" for term in args.keywords.split(","))
    logging.info(f"Searching GitHub for repositories with keywords: {args.keywords}")
    
    repositories = search_github_repositories(search_query, args.min_stars, args.min_forks)
    processed_repos = process_repositories(repositories, args.min_stars, args.min_forks)
    
    logging.info(f"Found {len(processed_repos)} repositories after filtering.")
    save_to_json(processed_repos, args.output)

if __name__ == "__main__":
    main()
