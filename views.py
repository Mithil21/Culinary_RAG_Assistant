# Author: Mithil Baria
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .assistant_core import get_assistant_response

@api_view(['POST'])
def ask_assistant(request):
    """Receives the full chat history from Angular."""
    # We now look for 'messages' instead of 'prompt'
    messages = request.data.get('messages', [])

    if not messages:
        return Response({"error": "No messages provided"}, status=status.HTTP_400_BAD_REQUEST)

    # The last message in the array is the user's current question
    latest_message = messages[-1].get('content', '')
    
    # Everything before the last message is the history
    chat_history = messages[:-1] 

    print(f"\n[API] Received question: {latest_message}")
    print(f"[API] History length: {len(chat_history)} messages")

    # Pass BOTH into the brain
    response_data = get_assistant_response(latest_message, chat_history)

    return Response(response_data, status=status.HTTP_200_OK)