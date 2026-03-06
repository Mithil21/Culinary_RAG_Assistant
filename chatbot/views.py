from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Import the brain! 
# (This will trigger the model to load into memory when Django starts)
from .assistant_core import get_assistant_response

@api_view(['POST'])
def ask_assistant(request):
    """
    Receives a prompt from Angular, passes it to LangGraph,
    and returns the generated answer and retrieved chunks.
    """
    user_prompt = request.data.get('prompt')

    if not user_prompt:
        return Response({"error": "No prompt provided"}, status=status.HTTP_400_BAD_REQUEST)

    print(f"\n[API] Received prompt: {user_prompt}")

    # Pass the prompt to our pre-loaded LangGraph workflow
    response_data = get_assistant_response(user_prompt)

    # Return the structured JSON output
    return Response(response_data, status=status.HTTP_200_OK)