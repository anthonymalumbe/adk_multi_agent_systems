import logging
import google.cloud.logging
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse
from google.adk.models.llm_request import LlmRequest

def log_query_to_model(callback_context: CallbackContext, llm_request: LlmRequest):
    """Initialises a Google Cloud Logging client and logs the last user query.

    This function inspects the outgoing LLM request to find the last message
    from the 'user'. If found, its text content is logged to Google Cloud
    Logging, prefixed with the agent's name.

    Args:
        callback_context: The context object for the agent callback. It contains
                          state and configuration, such as the `agent_name`.
        llm_request: The request object being sent to the language model. This
                     function inspects its `contents` to find the user's query.
    """
    # Initialize the client to send logs to Google Cloud Logging.
    cloud_logging_client = google.cloud.logging.Client()
    cloud_logging_client.setup_logging()

    # Check if there are any contents and if the last message is from the 'user'.
    if llm_request.contents and llm_request.contents[-1].role == 'user':
        last_message = llm_request.contents[-1]
        
        # Ensure the message has parts and the first part contains text.
        # This prevents errors if the message part is empty or not text-based.
        if last_message.parts and last_message.parts[0].text:
            last_user_message = last_message.parts[0].text
            
            # Log the user's message, including it directly in the f-string
            # to handle all types gracefully and improve readability.
            logging.info(f"[query to {callback_context.agent_name}]: {last_user_message}")

def log_model_response(callback_context: CallbackContext, llm_response: LlmResponse):
    """Initialises a Google Cloud Logging client and logs the model's response.

    This function processes the response from the LLM. It iterates through the
    content parts and logs either the text content or the name of any
    function calls made by the model.

    Args:
        callback_context: The context object for the agent callback, used here
                          to retrieve the `agent_name` for the log entry.
        llm_response: The response object received from the language model. Its
                      `content.parts` are processed for logging.
    """
    # Initialize the client to send logs to Google Cloud Logging.
    cloud_logging_client = google.cloud.logging.Client()
    cloud_logging_client.setup_logging()

    # Check if the response contains any content parts to process.
    if llm_response.content and llm_response.content.parts:
        # A response can be multi-part, so iterate through each part.
        for part in llm_response.content.parts:
            # Check if the part contains text and log it.
            if part.text:
                # Log the text response, including it directly in the f-string.
                logging.info(f"[response from {callback_context.agent_name}]: {part.text}")
            # Alternatively, check if the part is a function call and log its name.
            elif part.function_call:
                # Log the function call, including its name in the f-string.
                logging.info(f"[function call from {callback_context.agent_name}]: {part.function_call.name}")
