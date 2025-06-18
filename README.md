# Context AI 
## A Multi-Agent System for Fact-Checking and Content Refinement

![Alt text](https://github.com/anthonymalumbe/adk_multi_agent_systems/blob/master/images/a2a_framework.png Multi-modal, (A2A) Multi-Agent System)

A sophisticated multi-agent framework that critically evaluates, researches, and refines text-based content. Built with the Google Agent Development Kit (ADK) and Streamlit, Context AI combines specialized AI agents to ensure accuracy, depth, and and clarity—supporting both text and voice interactions.

---

## Architecture Overview

The core of this application is the **`llm_news_auditor`**, a top‑level agent orchestrating a sequential pipeline of sub-agents:

1. **Investigative Journalist**

   * Decomposes input text into discrete factual claims.
   * Queries news sources and fact‑checking databases to verify each claim.
   * Labels claims (Accurate, Inaccurate, Disputed) with supporting evidence.

2. **Meticulous Researcher**

   * Gathers additional background from Wikipedia and other reference sources.
   * Provides context, historical details, and deeper insights.

3. **News Editor**

   * Integrates the journalist’s and researcher’s findings into the original content.
   * Corrects inaccuracies, clarifies disputes, and enriches with new details.
   * Preserves the author’s tone, style, and structure with minimal edits.
---
```bash
Folder Structure

context-ai/
├── .venv/                      # Virtual environment directory created by uv
├── adk_multi_agent_systems/
│   ├── llm_news_agents/
│   │   ├── sub_agents/
│   │   │   ├── investigative_journalist/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py
│   │   │   │   └── prompt.py
│   │   │   ├── news_researcher/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── agent.py
│   │   │   │   └── prompt.py
│   │   │   └── news_editor/
│   │   │       ├── __init__.py
│   │   │       ├── agent.py
│   │   │       └── prompt.py
│   │   ├── __init__.py
│   │   └── agent.py
│   ├── apps/
│   │   └── context_ai.py
│   ├── utils/
│   │   └── utils.py
│   └── callback_logging.py
├── .env                        # For storing API keys and environment variables
├── .gitignore                  # Git ignore file
├── pyproject.toml              # Project metadata and dependencies
├── requirements.txt            # Project dependencies
└── README.md                   # This file
```
---

## Key Features

* **Multi‑Agent Workflow:** Modular agents collaborate to ensure robust, multi‑faceted analysis.
* **Automated Fact‑Checking:** Integrates news APIs and fact‑checking tools for real‑time verification.
* **Content Enrichment:** Adds valuable context, background, and expert perspective.
* **Intelligent Editing:** Maintains original voice and structure while ensuring factual accuracy.
* **Interactive UI:** Streamlit-based chat interface with both text and voice I/O.
* **Detailed Logging:** Google Cloud Logging captures agent interactions and tool usage for audit and debugging.

---

## Prerequisites

* **Python** ≥ 3.13
* **Google Cloud Project** with the following APIs enabled:

  * Speech-to-Text
  * Text-to-Speech
  * Cloud Logging
  * Google Gemini [Google AI Studio](https://aistudio.google.com/).
---

## Obtaining a Gemini API Key

1. Navigate to [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account and accept the Terms of Service if prompted.
3. Create or select an existing project.
4. In the sidebar, click **Get API key**.
5. Click **Create API key** and copy the displayed key.
----

## API Keys

* **API Keys** for:

  * NewsAPI ([Get started](https://newsapi.org/docs/get-started))
  * Newsdata ([Dashboard](https://newsdata.io/search-dashboard))
  * Google Fact Check API ([API docs](https://toolbox.google.com/factcheck/apis))

> **Security Tip:** Never expose your API key publicly or commit it to version control.
---

## Local Environment Setup with `uv`

We use [`uv`](https://astral.sh/uv) to manage our project environment and workflows.

### macOS / Linux

```bash
# Install uv
echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your terminal to load uv

# Initialize the project
directory="context-ai" uv init "$directory"
cd "$directory"

# Create and activate a virtual environment
uv venv
source .venv/bin/activate
```

### Windows (PowerShell)

```powershell
# Install uv
Write-Host "Installing uv..."
irm https://astral.sh/uv/install.ps1 | iex
# Restart PowerShell to load uv

# Initialize the project
dot-source uv.ps1 init context-ai
cd context-ai

# Create and activate a virtual environment
uv venv
.\.venv\Scripts\Activate.ps1
```

---

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/your-username/adk-multi-agent-systems.git
   cd adk-multi-agent-systems
   ```
2. Install dependencies in editable mode:

   ```bash
   uv pip install -e .
   uv pip install -r requirements.txt
   ```

---

## Configuration

1. In the project root, create a `.env` file.
2. Populate it with your API keys:

   ```env
   GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
   NEWSAPI_KEY="YOUR_NEWSAPI_KEY"
   NEWSDATA_API_KEY="YOUR_NEWSDATA_API_KEY"
   FACT_CHECKER_API_KEY="YOUR_FACT_CHECKER_API_KEY"
   ```
3. Authenticate Google Cloud:

   ```bash
   gcloud auth application-default login
   ```

---

## Usage

1. **Start the ADK server:**

   ```bash
   adk api_server
   ```
2. **Run the Streamlit app in a separate terminal:**

   ```bash
   streamlit run adk_multi_agent_systems/apps/context_ai.py
   ```
3. Open your browser at the URL shown by Streamlit to begin interacting with Context AI.

---

## Dependencies

* **google-generativeai:** SDK for Google Gemini models
* **google-adk:** Foundation for multi-agent orchestration
* **streamlit:** Interactive web interface
* **langchain:** Utilities for working with LLMs
* **google-cloud-speech & google-cloud-texttospeech:** Voice I/O support
* **newsapi-python:** Client for fetching news articles
* **wikipedia:** Programmatic access to Wikipedia content

---

## Logging & Monitoring

All agent interactions and tool calls are logged to Google Cloud Logging. Configure sinks and views in the Cloud Console to analyze logs and metrics.
