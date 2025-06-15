"""News editor agent for correcting inaccuracies based on verified findings."""

import asyncio
import os
import requests

from typing import Optional, List, Dict

from google.adk import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import google_search
from google.genai import types


from . import prompt

_END_OF_EDIT_MARK = '---END-OF-EDIT---'


async def _remove_end_of_edit_mark(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Removes the end-of-edit marker from the final output."""
    del callback_context  # unused
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
    for idx, part in enumerate(llm_response.content.parts):
        if part.text and _END_OF_EDIT_MARK in part.text:
            del llm_response.content.parts[idx + 1 :]
            part.text = part.text.split(_END_OF_EDIT_MARK, 1)[0]
    return llm_response


async def _render_reference(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Appends grounding references to the response from Google Search."""
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
        elif chunk.web:
            title = chunk.web.title
            uri = chunk.web.uri
        
        parts = [s for s in (title, text) if s]
        if uri and parts:
            parts[0] = f'[{parts[0]}]({uri})'
        if parts:
            references.append('* ' + ': '.join(parts) + '\n')
            
    if references:
        reference_text = ''.join(['\n\nReferences:\n\n'] + references)
        llm_response.content.parts.append(types.Part(text=reference_text))
        
    return llm_response


async def final_processing_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Combines reference rendering and cleanup into a single callback."""
    # First, render the references from the Google Search grounding
    llm_response = await _render_reference(callback_context, llm_response)
    # Then, remove the end-of-edit marker
    llm_response = await _remove_end_of_edit_mark(callback_context, llm_response)
    return llm_response


news_editor_agent = Agent(
    model='gemini-2.0-flash',
    name='news_editor_agent',
    instruction=prompt.news_editor_PROMPT,
    # Added Google Search for the final grounding step
    tools=[google_search],
    after_model_callback=final_processing_callback,
)
