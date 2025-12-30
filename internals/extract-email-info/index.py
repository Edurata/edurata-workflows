import re


def handler(inputs):
    """
    Extrahiert Informationen aus dem E-Mail-Body mittels Regex.
    Extrahiert Primary Key für Airtable und die eigentliche Nachricht.
    
    Args:
        inputs: Dictionary containing:
            - content: Email body content
            - messageId: Message ID
            - threadId: Thread ID
            - primary_key_regex: Regex pattern to extract primary key
            - message_regex: Regex pattern to extract message content
    
    Returns:
        Dictionary with:
            - messageId: Original message ID
            - threadId: Original thread ID
            - primaryKey: Extracted primary key (empty string if not found)
            - message: Extracted message content (full content if not found)
            - originalContent: Original email content
    """
    content = inputs.get("content", "")
    primary_key_regex = inputs.get("primary_key_regex", "")
    message_regex = inputs.get("message_regex", "")
    
    primary_key = None
    message = content  # Default to full content if regex doesn't match
    
    # Extract primary key
    if primary_key_regex:
        match = re.search(primary_key_regex, content, re.MULTILINE | re.DOTALL)
        if match:
            primary_key = match.group(1) if match.groups() else match.group(0)
    
    # Extract message content
    if message_regex:
        match = re.search(message_regex, content, re.MULTILINE | re.DOTALL)
        if match:
            message = match.group(1) if match.groups() else match.group(0)
            # Strip whitespace from extracted message
            message = message.strip()
    
    return {
        "messageId": inputs.get("messageId"),
        "threadId": inputs.get("threadId"),
        "primaryKey": primary_key or "",
        "message": message,
        "originalContent": content
    }

