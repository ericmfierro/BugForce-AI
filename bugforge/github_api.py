"""Narrow GitHub REST API adapter; no arbitrary API requests from model text."""
import re
import requests
from .store import similarity

REPO_PATTERN = re.compile(r'^[\w.-]+/[\w.-]+$')


class GitHubError(RuntimeError):
    pass


class GitHubIssues:
    def __init__(self, repo: str, token: str = ''):
        if not REPO_PATTERN.fullmatch(repo or ''):
            raise ValueError('GitHub repository must be in owner/repo format.')
        self.repo = repo
        self.token = token
        self.base = f'https://api.github.com/repos/{repo}'

    def _headers(self) -> dict:
        headers = {'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28',
                   'User-Agent': 'BugForgeAI-Class-Project'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def similar_issues(self, title: str):
        try:
            res = requests.get(f'{self.base}/issues', params={'state': 'all', 'per_page': 50},
                               headers=self._headers(), timeout=10)
            res.raise_for_status()
        except requests.RequestException as exc:
            raise GitHubError('Could not check existing GitHub issues.') from exc
        hits = []
        for item in res.json():
            if 'pull_request' in item:
                continue
            score = similarity(title, item.get('title', ''))
            if score >= 0.63:
                hits.append({'title': item['title'], 'score': score, 'source': 'GitHub issue',
                             'url': item.get('html_url', ''), 'id': str(item['number'])})
        return sorted(hits, key=lambda x: x['score'], reverse=True)[:5]

    def create_issue(self, title: str, body: str) -> str:
        if not self.token:
            raise GitHubError('GitHub token is not configured.')
        try:
            response = requests.post(f'{self.base}/issues',
                                     json={'title': title[:140], 'body': body[:60000]},
                                     headers=self._headers(), timeout=15)
            response.raise_for_status()
        except requests.HTTPError as exc:
            code = getattr(exc.response, 'status_code', None)
            raise GitHubError(f'GitHub rejected issue creation (HTTP {code}). Check token permissions.') from exc
        except requests.RequestException as exc:
            raise GitHubError('GitHub issue creation failed due to a network error.') from exc
        url = response.json().get('html_url', '')
        if not url.startswith('https://github.com/'):
            raise GitHubError('GitHub returned an unexpected issue URL.')
        return url
