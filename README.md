# BugForce-AI
BugForge AI is a Gemini-powered QA agent that analyzes game bugs, generates structured reports, and automates ticket creation and GitHub issue tracking.

# BugForge AI

**AI-Powered Game Bug Investigation and Reporting**

BugForge AI is a web-based quality assurance (QA) assistant powered by Google's Gemini API. It helps game developers and testers analyze software bugs, generate structured reports, and automate issue tracking.

Instead of manually documenting every bug, users can describe a problem in natural language. BugForge AI analyzes the description, identifies potential causes, recommends reproduction steps, and proposes actions that can be executed with user approval.

## Features

- **AI Bug Analysis:** Uses Google Gemini to analyze reported issues and provide detailed insights.
- **Severity Classification:** Categorizes bugs based on their potential impact.
- **Reproduction Steps:** Generates suggested steps to help developers investigate reported problems.
- **Automated Bug Reports:** Creates structured Markdown reports containing relevant investigation details.
- **Local Ticket Management:** Saves bug reports as tickets in a SQLite database.
- **GitHub Integration:** Supports publishing approved bug reports directly to GitHub Issues.
- **Duplicate Detection:** Identifies potentially similar existing issues.
- **Action History:** Maintains records of executed operations.
- **Safety Controls:** Validates proposed actions and requires user confirmation before execution.

## Technologies Used

- **Python:** Application logic and action execution
- **Google Gemini API:** AI-powered bug analysis
- **Streamlit:** Interactive web interface
- **SQLite:** Local ticket storage
- **Pydantic:** Structured response validation
- **GitHub REST API:** Issue tracking integration

## Getting Started

### Requirements

- Python 3.11 or newer
- Internet connection
- Google Gemini API key
- GitHub account and access token (optional)

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/ericmfierro/BugForce-AI.git
cd BugForce-AI
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

Using a Python virtual environment is recommended.

**3. Configure the Gemini API**

Create a file named `secrets.toml` inside the `.streamlit` directory, using `secrets.example.toml` as a template.

```toml
GEMINI_API_KEY = "your-api-key"
GEMINI_MODEL = "gemini-2.5-flash"

GITHUB_REPO = ""
GITHUB_TOKEN = ""
ADMIN_PIN = ""
```

You can obtain a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

GitHub configuration is optional and only required for GitHub-related features. To enable issue publishing, configure the target repository, a suitably restricted GitHub token, and a private owner PIN.

Never upload your actual API keys or access tokens to a public repository.

**4. Start the application**

```bash
python -m streamlit run app.py
```

Open the application in your browser at:

`http://localhost:8501`

## How to Use

1. Open the **Investigate bug** tab.
2. Describe the issue, including any observed behavior and relevant environment information.
3. Click **Analyze with Gemini**.
4. Review the generated analysis, severity, reproduction steps, and suggested tests.
5. Review the actions proposed by the agent.
6. Approve and execute the desired operations.
7. View saved reports under **Local tickets** and execution records under **Action history**.

### Example Request

> After respawning in a multiplayer game, my character sometimes freezes when switching weapons. The issue lasts approximately five seconds and prevents movement or shooting. Analyze the problem, generate reproduction steps, create a local ticket, and save a bug report.

BugForge AI will analyze the request and generate a structured investigation. After approval, it can create the local ticket and save the report.

## Supported Actions

| Action | Description |
|---|---|
| Save Report | Generates and saves a Markdown bug report |
| Create Ticket | Creates a record in the local SQLite database |
| Publish GitHub Issue | Publishes an approved report to a configured GitHub repository |

All operations are validated before execution. BugForge AI does not execute arbitrary system commands.

## Security and Limitations

BugForge AI requires user approval before executing proposed actions. GitHub publishing also requires owner authorization.

AI-generated analysis is intended to assist investigation. Suggested causes and reproduction steps are not guaranteed to be accurate and should be verified through testing.

Local tickets and reports are stored in session-specific directories. On cloud hosting services with temporary storage, these records may not persist after an application restart.

Users should avoid submitting confidential project information or credentials.

## Running Tests

To execute the automated tests:

```bash
pip install pytest
python -m pytest -q
```

## Future Improvements

Potential improvements include screenshot and video analysis, automatic log parsing, integrations with additional issue-tracking platforms, and more advanced duplicate detection.

## Project Repository

[BugForge AI on GitHub](https://github.com/ericmfierro/BugForce-AI)
