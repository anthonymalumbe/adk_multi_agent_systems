"""investigative journalist agent for identifying and verifying statements using search tools."""
import os
import sys
import logging
import google.cloud.logging
import requests
import asyncio
import httpx

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from callback_logging import log_query_to_model, log_model_response
from newsdataapi import NewsDataApiClient
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from . import prompt

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))
logger = logging.getLogger(__name__)

async def _render_reference(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Appends formatted grounding references to an LLM response and consolidates content.

    This function processes grounding metadata from an `LlmResponse`. If such
    metadata exists, it formats the references into a markdown list, appends
    this list to the response content, and then consolidates all text parts
    into a single part for a clean, unified output.

    Args:
        callback_context: The context for the callback, containing state and
          configuration. It is not used in this specific function.
        llm_response: The response object from the Language Model, potentially
          containing content and grounding metadata.

    Returns:
        The modified `LlmResponse` object with formatted references appended
        and content consolidated.
    """
    del callback_context
    if (
        not llm_response.content or
        not llm_response.content.parts or
        not llm_response.grounding_metadata
    ):
        return llm_response
    
    references = []
    # Iterate through each grounding chunk provided in the metadata.
    for chunk in llm_response.grounding_metadata.grounding_chunks or []:
        title, uri, text = '', '', ''
        # Extract details from either 'retrieved_context' or 'web' sources.
        if chunk.retrieved_context:
            title = chunk.retrieved_context.title
            uri = chunk.retrieved_context.uri
            text = chunk.retrieved_context.text
        elif chunk.web:
            title = chunk.web.title
            uri = chunk.web.uri
        
        # Collect non-empty parts (title, text) for the reference string.
        parts = [s for s in (title, text) if s]
        if uri and parts:
            # Format the first part as a markdown link if a URI exists.
            parts[0] = f'[{parts[0]}]({uri})'
        if parts:
            # Join the parts and format as a list item.
            references.append('* ' + ': '.join(parts) + '\n')
   
    # If any references were generated, append them to the response content.        
    if references:
        reference_text = ''.join(['\n\nReference:\n\n'] + references)
        llm_response.content.parts.append(types.Part(text=reference_text))

    # Consolidate all text parts into a single part for cleaner output.
    # This avoids multiple, fragmented text sections in the final display.
    valid_text_parts = [part.text for part in llm_response.content.parts if part.text is not None]
    if valid_text_parts:
        all_text = '\n'.join(valid_text_parts)
        # Overwrite the first part with the combined text.
        llm_response.content.parts[0].text = all_text
        # Remove all subsequent parts as their content is now in the first part.
        if len(llm_response.content.parts) > 1:
            del llm_response.content.parts[1:]
        
    return llm_response

async def fetch_top_newsdataio_api(query: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Asynchronously searches for news articles using the NewsAPI 'everything' endpoint.

    This function handles API calls asynchronously, validates date formats, and gracefully
    manages potential web errors. If dates are not provided, it defaults to searching
    the last 7 days.

    Args:
        query (str): The keyword or phrase to search for.
        from_date (Optional[str]): The oldest date for articles (YYYY-MM-DD). 
                                 Defaults to 7 days before the to_date.
        to_date (Optional[str]): The newest date for articles (YYYY-MM-DD). 
                               Defaults to the current date.

    Returns:
        A list of article dictionaries, or an empty list if an error occurs.
    
    Raises:
        ValueError: If the provided date format is incorrect.
    """
    # It's a best practice to get sensitive keys from environment variables
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        print("Error: 'NEWSAPI_KEY' environment variable not set.")
        return []

    url = "https://newsapi.org/v2/everything"
    
    # Set headers, including User-Agent, to prevent certain connection errors
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }

    params = {
        "q": query,
        "sortBy": "relevancy",
        "pageSize": 5,
        "page": 1,
        "language": "en",
        "apiKey": api_key
    }

    # Set default dates if they are not provided
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    
    if from_date is None:
        try:
            # Calculate 7 days prior to the effective 'to_date'
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d")
            from_date_obj = to_date_obj - timedelta(days=7)
            from_date = from_date_obj.strftime("%Y-%m-%d")
        except ValueError:
            raise ValueError("to_date must be in YYYY-MM-DD format to calculate default from_date.")


    # Validate and add date parameters. This handles both provided and default dates.
    try:
        # Validate the date format
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        params["from"] = from_dt.strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("from_date must be in YYYY-MM-DD format.")

    try:
        # Validate the date format
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        params["to"] = to_dt.strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("to_date must be in YYYY-MM-DD format.")

    try:
        # Use httpx.AsyncClient for making asynchronous web requests
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            # Raise an exception for bad status codes (4xx or 5xx)
            response.raise_for_status()  
            data = response.json()

        # Extract only the desired fields from the articles
        filtered_articles = []
        for article in data.get("articles", []):
            filtered_articles.append({
                "source": article.get("source", {}).get("name"),
                "title": article.get("title"),
                "description": article.get("description"),
                "url": article.get("url")
            })
        return filtered_articles

    except httpx.HTTPStatusError as e:
        # Handle HTTP errors gracefully
        print(f"Error searching news: HTTP {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        # Handle network-related errors
        print(f"Error searching news: A network error occurred - {e}")
        return []
    except Exception as e:
        # Handle other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return []
    
async def search_news(query: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for news articles matching a query using NewsAPI's 'everything' endpoint.

    Args:
        query (str): The keyword or phrase to search for.
        api_key (str): Your NewsAPI API key.
        from_date (Optional[str]): The oldest date for articles (YYYY-MM-DD). Defaults to None.
        to_date (Optional[str]): The newest date for articles (YYYY-MM-DD). Defaults to None.

    Returns:
        list: A list of up to 5 article dictionaries, sorted by popularity.
    
    Raises:
        ValueError: If the provided date format is incorrect.
        requests.exceptions.RequestException: For issues with the web request.
        Exception: If the API returns an error status.
    """
    api_key = os.getenv("NEWSAPI_KEY")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "relevancy",
        "pageSize": 5,
        "page": 1,
        "language": "en",
        "apiKey": api_key
    }

    # Add 'from' date to parameters if it's provided
    if from_date:
        try:
            # Validate the date format
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            params["from"] = from_dt.strftime("%Y-%m-%d")
        except ValueError:
            # Raise an error for an invalid format
            raise ValueError("from_date must be in YYYY-MM-DD format.")

    # Add 'to' date to parameters if it's provided
    if to_date:
        try:
            # Validate the date format
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            params["to"] = to_dt.strftime("%Y-%m-%d")
        except ValueError:
            # Raise an error for an invalid format
            raise ValueError("to_date must be in YYYY-MM-DD format.")

    # Make the API request
    response = requests.get(url, params=params)
    response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
    data = response.json()

    filtered = []
    for article in data.get("articles", []):
        filtered.append({
            "source": article.get("source"),          
            "title": article.get("title"),
            "description": article.get("description"),
            "url": article.get("url")
        })

    return filtered

async def fact_checker(
    query: str,
    language_code: str = "en-US",
    max_age_days: int = 30,
    page_size: int = 10,
) -> Optional[List[Dict]]:
    """
    Searches the Google Fact Check Tools API for claims matching the given query.
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
        response.raise_for_status()
        data = response.json()
        if "claims" not in data:
            return []
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
        print(f"Error making API request: {e}")
        return None

investigative_journalist_agent = Agent(
    model='gemini-1.5-flash',
    name='investigative_journalist',
    before_model_callback=log_query_to_model,
    after_model_callback=_render_reference,
    instruction=prompt.investigative_journalist_PROMPT,
    tools=[fetch_top_newsdataio_api,search_news, fact_checker],
)
