"""LLM Auditor for verifying & refining LLM-generated answers using the web."""
import sys
from google.adk.agents import SequentialAgent
from .sub_agents.investigative_journalist import investigative_journalist_agent
from .sub_agents.news_researcher import research_agent
from .sub_agents.news_editor import news_editor_agent

from callback_logging import log_query_to_model, log_model_response

sys.path.append("..")

llm_news_agent = SequentialAgent(
    name='llm_news_auditor',
    sub_agents=[investigative_journalist_agent, research_agent, news_editor_agent], 
    description=(
        "Orchestrates a sequential auditing pipeline where an investigative "
        "journalist first targets potential inaccuracies, a researcher verifies "
        "facts against live web data, and an editor synthesizes the findings "
        "into a polished, truthful final report."
    ),

)

root_agent = llm_news_agent