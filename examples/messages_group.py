from msgspec import Struct

from starapi import Group, Request, Response, route


# Define the payload
class EditMessagePayload(Struct):
    content: str


# Define the response
class EditMessageSuccessResponse(Struct):
    success: bool
    new_content: str
    message: str


# Define the group (like a cog)
class MessagesGroup(Group, prefix="messages"):
    @route.patch(
        "/{message_id}",
        responses={200: EditMessageSuccessResponse},  # Passing the responses for docs
        payload=EditMessagePayload,  # Passing the payload for docs
    )
    async def edit_message(
        self, request: Request, message_id: int
    ) -> Response:  # path params are added as annotated kwargs to easily get the annotation
        """
        Edits a message.
        """

        # Fetching the payload
        payload: EditMessagePayload = await request.payload()

        # Generating the response's data
        data = EditMessageSuccessResponse(
            True, payload.content, "Message has been edited"
        )
        # Returning the response
        return Response.ok(data)
