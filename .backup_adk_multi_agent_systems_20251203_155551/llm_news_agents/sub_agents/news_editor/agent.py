"""News editor agent for correcting inaccuracies based on verified findings."""
import asyncio
import os
import requests

from typing import Optional, List, Dict
from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.tools.google_search_tool import google_search
from google.genai import types
from . import prompt

_END_OF_EDIT_MARK = '---END-OF-EDIT---'

async def _remove_end_of_edit_mark(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Removes the end-of-edit marker from the final language model output.

    This function searches for a specific marker ('---END-OF-EDIT---') within the
    response content. If found, it truncates the text at that point and removes
    any subsequent parts of the response, ensuring a clean final output.

    Args:
        callback_context (CallbackContext): The context object for the callback,
            provided by the agent framework. It is not used in this function.
        llm_response (LlmResponse): The response object from the language model
            which may contain the end-of-edit marker.

    Returns:
        LlmResponse: The modified response object with the marker and any
            subsequent content removed.
    """
    del callback_context  # Mark callback_context as intentionally unused.

    # If the response or its parts are empty, return it as is.
    if not llm_response.content or not llm_response.content.parts:
        return llm_response

    # Iterate through the parts of the response to find the marker.
    for idx, part in enumerate(llm_response.content.parts):
        if part.text and _END_OF_EDIT_MARK in part.text:
            # When the marker is found, remove all subsequent parts of the response.
            del llm_response.content.parts[idx + 1 :]
            # Truncate the current part's text to remove the marker and anything after it.
            part.text = part.text.split(_END_OF_EDIT_MARK, 1)[0]
            # Stop searching after the first marker is found and processed.
            break
    return llm_response


async def _render_reference(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Appends formatted grounding references from Google Search to the response.

    This function processes grounding metadata attached to the LLM response,
    formats it into a readable 'References' section with markdown links, and
    appends it to the response content.

    Args:
        callback_context (CallbackContext): The context object for the callback,
            which is not used in this function.
        llm_response (LlmResponse): The response object from the language model,
            containing grounding metadata from search results.

    Returns:
        LlmResponse: The modified response object with a new 'References'
            section appended, if grounding metadata was available.
    """
    del callback_context # Mark callback_context as intentionally unused.

    # Check if there is content and grounding metadata to process.
    if (
        not llm_response.content or
        not llm_response.content.parts or
        not llm_response.grounding_metadata
    ):
        return llm_response

    references = []
    # Loop through each grounding chunk provided in the metadata.
    for chunk in llm_response.grounding_metadata.grounding_chunks or []:
        title, uri, text = '', '', ''
        # Extract title and URI from different possible grounding sources.
        if chunk.retrieved_context:
            title = chunk.retrieved_context.title
            uri = chunk.retrieved_context.uri
        elif chunk.web:
            title = chunk.web.title
            uri = chunk.web.uri

        # Collect the parts of the reference that are not empty.
        parts = [s for s in (title, text) if s]
        if uri and parts:
            # Format the title as a markdown link if a URI is available.
            parts[0] = f'[{parts[0]}]({uri})'
        if parts:
            # Join the parts into a single reference line and add to the list.
            references.append('* ' + ': '.join(parts) + '\n')

    # If any references were successfully formatted, append them to the response.
    if references:
        # Combine all references into a single text block.
        reference_text = ''.join(['\n\nReferences:\n\n'] + references)
        # Add the reference text as a new part of the response content.
        llm_response.content.parts.append(types.Part(text=reference_text))

    return llm_response


async def final_processing_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Combines reference rendering and cleanup into a single final callback.

    This function orchestrates the final processing of the language model's
    response by executing a sequence of helper functions. It first appends
    grounding references and then cleans up any internal markers.

    Args:
        callback_context (CallbackContext): The context object for the callback,
            which is passed to the helper functions.
        llm_response (LlmResponse): The initial response object from the
            language model that requires final processing.

    Returns:
        LlmResponse: The fully processed and cleaned response object, ready to
            be sent to the user.
    """
    # First, render the references from the Google Search grounding.
    llm_response = await _render_reference(callback_context, llm_response)
    # Second, remove the end-of-edit marker for a clean final output.
    llm_response = await _remove_end_of_edit_mark(callback_context, llm_response)
    return llm_response

news_editor_agent = Agent(
    model='gemini-2.5-flash-lite',
    name='news_editor_agent',
    instruction=prompt.news_editor_PROMPT,
    # Added Google Search for the final grounding step
    tools=[google_search],
    after_model_callback=final_processing_callback,
)
