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


# Agents
research_agent = Agent(
    name="researcher",
    model='gemini-2.5-flash-lite',
    description="Answer research questions using fetch_top_articles tool.",
    instruction=instruction=prompt.researcher_PROMPT,
    generate_content_config=types.GenerateContentConfig(
    temperature=0,
    ),
    tools=[
        LangchainTool(tool=WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())),
        append_to_state,
    ],
)
