import os
import logging
import google.cloud.logging
import requests

from typing import Optional, List, Dict
from dotenv import load_dotenv
from datetime import datetime

from google.adk import Agent
from google.adk.agents import SequentialAgent, LoopAgent, ParallelAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.langchain_tool import LangchainTool  # import
from google.adk.tools.crewai_tool import CrewaiTool
from google.genai import types

from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from crewai_tools import FileWriterTool

cloud_logging_client = google.cloud.logging.Client()
cloud_logging_client.setup_logging()
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Configure a simple console handler if nothing is set
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Tools
def append_to_state(
    tool_context: ToolContext, field: str, response: str
) -> dict[str, str]:
    """Append new output to an existing state key.

    Args:
        field (str): a field name to append to
        response (str): a string to append to the field

    Returns:
        dict[str, str]: {"status": "success"}
    """
    existing_state = tool_context.state.get(field, [])
    tool_context.state[field] = existing_state + [response]
    logging.info(f"[Added to {field}] {response}")
    return {"status": "success"}

def fetch_top_articles(
#     from_date: str = None,
#     to_date: str = None,
#     sort_by: str = "publishedAt"
# ):
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sort_by: str = "publishedAt"
) -> List[Dict[str, Optional[str]]]:
    """
    Fetches the top 10 articles from a fixed list of global sources with optional keyword search and date range.

    Parameters:
    -----------
    q : Optional[str]
        Keywords or phrases to search for in the article title and body. Supports advanced syntax:
          - Exact phrases: surround with double quotes, e.g. `"climate change"`
          - Must include: prepend with '+', e.g. `+bitcoin`
          - Must exclude: prepend with '-', e.g. `-bitcoin`
          - Boolean operators: AND, OR, NOT, and grouping with parentheses, e.g. `crypto AND (ethereum OR litecoin) NOT bitcoin`
        The entire string should be URL-encodable and ≤ 500 characters.

    from_date : Optional[str]
        Starting date filter in "DD-MM-YYYY" format. If provided, converted internally to "YYYY-MM-DD".
        Example: `"01-05-2025"`.
        If omitted, no lower bound on published date.

    to_date : Optional[str]
        Ending date filter in "DD-MM-YYYY" format. If provided, converted internally to "YYYY-MM-DD".
        Example: `"15-05-2025"`.
        If omitted, no upper bound on published date.

    sort_by : str
        One of `"publishedAt"`, `"popularity"`, or `"relevancy"`.
        Default is `"publishedAt"` to get the most recent.

    Returns:
    --------
    List[Dict[str, Optional[str]]]
        A list (up to 10 items) of dictionaries, each containing:
          - "author"  (str or None)
          - "url"     (str)
          - "headline" (str or None)  – if both title and description exist, uses description; otherwise picks whichever is non-empty
          - "content" (str or None)
        If the API call fails or parameters are invalid, returns an empty list and logs a warning.
    """
    # Fixed, comma-separated list of source IDs (9 global providers)
    all_sources = (
        "bbc-news,"
        "al-jazeera-english,"
        "associated-press,"
        "reuters,"
        "xinhua-net,"
        "deutsche-welle,"
        "france24,"
        "cnn,"
        "sky-news"
    )

    # Read API key from environment
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        logger.warning("Environment variable NEWSAPI_KEY is not set.")
        return []

    # Base endpoint for /v2/everything
    endpoint = "https://newsapi.org/v2/everything"

    # Build query parameters
    query_params = {
        "apiKey": api_key,
        "sources": all_sources,
        "sortBy": sort_by,
        "pageSize": 10
    }

    # Validate and include `q` if provided
    if q:
        if len(q) > 500:
            logger.warning("Parameter 'q' exceeds 500 characters.")
            return []
        query_params["q"] = q  # requests will handle URL-encoding

    # Helper: convert "DD-MM-YYYY" → "YYYY-MM-DD"
    def _parse_ddmmyyyy(date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%d-%m-%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Date '{date_str}' is not in DD-MM-YYYY format.")

    # Validate and include date filters
    if from_date:
        try:
            query_params["from"] = _parse_ddmmyyyy(from_date)
        except ValueError as ve:
            logger.warning(f"Invalid from_date: {ve}")
            return []
    if to_date:
        try:
            query_params["to"] = _parse_ddmmyyyy(to_date)
        except ValueError as ve:
            logger.warning(f"Invalid to_date: {ve}")
            return []

    # Perform the HTTP GET
    try:
        response = requests.get(endpoint, params=query_params)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.warning(f"NewsAPI request failed: {e}")
        return []

    data = response.json()
    if data.get("status") != "ok":
        message = data.get("message", "No message provided.")
        logger.warning(f"NewsAPI returned error status: {message}")
        return []

    articles = data.get("articles", [])
    results: List[Dict[str, Optional[str]]] = []

    for art in articles[:10]:
        author = art.get("author")
        url = art.get("url")
        title = art.get("title") or ""
        description = art.get("description") or ""
        content = art.get("content")

        # Compute "headline": if both title & description exist, use description; otherwise pick whichever is non-empty.
        if title and description:
            headline = description
        else:
            headline = title or description or None

        results.append({
            "author": author,
            "url": url,
            "headline": headline,
            "content": content
        })

    return results

# Agents

research_agent = Agent(
    name="researcher",
    model='gemini-2.0-flash',
    description="Answer research questions using fetch_top_articles tool.",
    instruction="""
    PROMPT:
    {{ PROMPT? }}
    
    PLOT_OUTLINE:
    {{ PLOT_OUTLINE? }}

    CRITICAL_FEEDBACK:
    {{ CRITICAL_FEEDBACK? }}

    INSTRUCTIONS:
    - If there is a CRITICAL_FEEDBACK, use your tools to do research to solve those suggestions
    - If there is a PLOT_OUTLINE, use your tools to do research to add more historical detail
    - If these are empty, use your tools to gather facts about the person in the PROMPT
    - Use the 'append_to_state' tool to add your research to the field 'research'.
    - Summarise what you have learned.
    Now, use your tools to do research.
    """,
    generate_content_config=types.GenerateContentConfig(
        temperature=0,
    ),
    tools=[
        fetch_top_articles,
        LangchainTool(tool=WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())),
        append_to_state,
    ],
)

    # - If there is a CRITICAL_FEEDBACK, use your wikipedia tool to do research to solve those suggestions
    # - If there is a PLOT_OUTLINE, use your wikipedia tool to do research to add more historical detail
    # - If these are empty, use your Wikipedia tool to gather facts about the person in the PROMPT
    # - Use the 'append_to_state' tool to add your research to the field 'research'.
    # - Summarise what you have learned.
    # Now, use your Wikipedia tool to do research.