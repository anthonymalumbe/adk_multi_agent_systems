investigative_journalist_PROMPT = """
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
    - Summarise what you have learned.
    Now, use your tools to do research.
    """ 
