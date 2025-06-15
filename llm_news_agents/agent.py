"""LLM Auditor for verifying & refining LLM-generated answers using the web."""
import sys
from google.adk.agents import SequentialAgent

from .sub_agents.investigative_journalist import investigative_journalist_agent
from .sub_agents.news_researcher import research_agent
from .sub_agents.news_editor import news_editor_agent

from callback_logging import log_query_to_model, log_model_response

sys.path.append("..")

llm_auditor = SequentialAgent(
    name='llm_news_auditor',
    description=(
        'Evaluates LLM-generated answers, verifies actual accuracy using the'
        ' web, and refines the response to ensure alignment with real-world'
        ' knowledge.'
    ),
    # The new sequence is more logical: the journalist investigates and produces
    # findings, and the editor uses those findings to revise the text.
    sub_agents=[investigative_journalist_agent, research_agent, news_editor_agent],
)

root_agent = llm_auditor

