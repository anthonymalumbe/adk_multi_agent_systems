"""investigative journalist agent for identifying and verifying statements using search tools."""
import os
import logging
import google.cloud.logging
import requests

from typing import Optional, List, Dict
from dotenv import load_dotenv
#from datetime import datetime


# import logging
import sys

from google.adk import Agent, tools
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.adk.tools import google_search
from google.genai import types

from callback_logging import log_query_to_model, log_model_response

from . import prompt


# Configure a basic logger
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
logger = logging.getLogger(__name__)

async def _render_reference(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Appends grounding references to the response."""
    del callback_context
    if (
        not llm_response.content or
        not llm_response.content.parts or
        not llm_response.grounding_metadata
    ):
        return llm_response
    
    references = []
    for chunk in llm_response.grounding_metadata.grounding_chunks or []:
        title, uri, text = '', '', ''
        if chunk.retrieved_context:
            title = chunk.retrieved_context.title
            uri = chunk.retrieved_context.uri
            text = chunk.retrieved_context.text
        elif chunk.web:
            title = chunk.web.title
            uri = chunk.web.uri
        
        parts = [s for s in (title, text) if s]
        if uri and parts:
            parts[0] = f'[{parts[0]}]({uri})'
        if parts:
            references.append('* ' + ': '.join(parts) + '\n')
            
    if references:
        reference_text = ''.join(['\n\nReference:\n\n'] + references)
        llm_response.content.parts.append(types.Part(text=reference_text))

    # --- START OF FIX ---
    # Create a list containing only the text from parts that are not None.
    # Pylance will correctly infer the type of `valid_text_parts` as list[str].
    valid_text_parts = [part.text for part in llm_response.content.parts if part.text is not None]

    # Your original logic was to proceed only if *all* parts had text.
    # This check preserves that exact logic in a type-safe way.
    if len(valid_text_parts) == len(llm_response.content.parts):
        # Now, join is guaranteed to receive only strings.
        all_text = '\n'.join(valid_text_parts)
        llm_response.content.parts[0].text = all_text
        del llm_response.content.parts[1:]
    # --- END OF FIX ---
        
    return llm_response

# Note: The following imports were part of your original snippet
# and are included for context. The types `CallbackContext`, `LlmResponse`,
# and `types` are assumed to be defined elsewhere.
#
# import requests
# from typing import List, Dict, Optional
#
# class CallbackContext: pass
# class LlmResponse: pass
# class types:
#     class Part:
#         text: Optional[str]

# async def _render_reference(
#     callback_context: CallbackContext,
#     llm_response: LlmResponse,
# ) -> LlmResponse:
#     """Appends grounding references to the response."""
#     del callback_context
#     if (
#         not llm_response.content or
#         not llm_response.content.parts or
#         not llm_response.grounding_metadata
#     ):
#         return llm_response
#     references = []
#     for chunk in llm_response.grounding_metadata.grounding_chunks or []:
#         title, uri, text = '', '', ''
#         if chunk.retrieved_context:
#             title = chunk.retrieved_context.title
#             uri = chunk.retrieved_context.uri
#             text = chunk.retrieved_context.text
#         elif chunk.web:
#             title = chunk.web.title
#             uri = chunk.web.uri
#         parts = [s for s in (title, text) if s]
#         if uri and parts:
#             parts[0] = f'[{parts[0]}]({uri})'
#         if parts:
#             references.append('* ' + ': '.join(parts) + '\n')
#     if references:
#         reference_text = ''.join(['\n\nReference:\n\n'] + references)
#         llm_response.content.parts.append(types.Part(text=reference_text))
#     if all(part.text is not None for part in llm_response.content.parts):
#         all_text = '\n'.join(part.text for part in llm_response.content.parts)
#         llm_response.content.parts[0].text = all_text
#         del llm_response.content.parts[1:]
#     return llm_response

# import requests
# from typing import List, Dict, Optional


def fact_checker(
    query: str,
    language_code: str = "en-US",
    max_age_days: int = 30,
    page_size: int = 10,
) -> Optional[List[Dict]]:
    """
    Searches the Google Fact Check Tools API for claims matching the given query.

    Args:
        query (str): The claim text or keywords to search (e.g., "climate change is a hoax").
        language_code (str): Language code for results (default "en-US").
        max_age_days (int): Only return claims reviewed in the last N days (default 30).
        page_size (int): Maximum number of claims to retrieve (default 10).

    Returns:
        A list of claim dictionaries if successful, or None if an error occurs.
        Each claim dictionary contains keys like:
          - 'text' (the claim text)
          - 'claimDate'
          - 'claimant'
          - 'claimReviews' (a list of review dicts with 'publisher', 'reviewDate', 'textualRating', 'url')
    """
    BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
    params = {
        "key": os.getenv("FACT_CHECKER_API_KEY"),
        "query": query,
        "languageCode": language_code,
        "maxAgeDays": max_age_days,
        "pageSize": page_size,
    }
    try:
        response = requests.get(BASE_URL, params=params)
        print(response.text)
        response.raise_for_status()
        data = response.json()

        if "claims" not in data:
            return []  # No claims found

        parsed_claims = []
        for claim in data["claims"]:
            claim_info = {
                "text": claim.get("text"),
                "claimDate": claim.get("claimDate"),
                "claimant": claim.get("claimant"),
                "claimReviews": [],
            }
            for review in claim.get("claimReview", []):
                claim_info["claimReviews"].append({
                    "publisher": review.get("publisher", {}).get("name"),
                    "reviewDate": review.get("reviewDate"),
                    "textualRating": review.get("textualRating"),
                    "url": review.get("url"),
                })
            parsed_claims.append(claim_info)

        return parsed_claims

    except requests.exceptions.RequestException as e:
        # In a real agent/tool, you might log this or return a special error message
        print(f"Error making API request: {e}")
        return None

# def get_current_date_time():
#     """
#     Returns the current date and time as a string.
#     """
#     now = datetime.now()
#     return now.strftime("%YYYY-%mm-%dd %H:%M:%S")

# CURRENT_DATE = get_current_date_time()

investigative_journalist_agent = Agent(
    # model='gemini-2.0-flash',
    model='gemini-1.5-flash-latest',
    name='investigative_journalist',
    before_model_callback=log_query_to_model,
    after_model_callback=_render_reference,
    instruction=prompt.investigative_journalist_PROMPT,
    # tools=[google_search, fact_checker],
    tools=[fact_checker],
    # tools=[fetch_top_articles],
    
)
