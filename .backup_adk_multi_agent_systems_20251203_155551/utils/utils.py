from datetime import datetime

def get_current_date_time(format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Gets the current local date and time and returns it as a formatted string.

    This function allows for custom formatting of the date and time string.
    If no format is specified, it defaults to 'YYYY-MM-DD HH:MM:SS'.

    Args:
        format_string (str, optional): A string that specifies the desired format
                                       for the output. It must follow the standard
                                       strftime() format codes. Defaults to
                                       "%Y-%m-%d %H:%M:%S".

    Returns:
        str: The current date and time formatted as a string according to the
             provided format_string.

    Example:
        >>> get_current_date_time()
        '2025-06-15 14:05:20'
        >>> get_current_date_time("%d/%m/%Y")
        '15/06/2025'
    """
    # Get the current local date and time using datetime.now()
    now = datetime.now()
    
    # Format the datetime object into a string using the provided format
    return now.strftime(format_string)


