import asyncio
from a2a.client import A2AClient
from uuid import uuid4

async def main():
    base_url = "http://localhost:10000/a2a"
    client = A2AClient(base_url)

    # Discover the agent
    card = await client.get_agent_card()
    print("Discovered agent:")
    print(card)

    # Send a query
    # message = Message(role="user", parts=[MessagePart(kind="text", text="Find papers on quantum computing")])
    # params = MessageSendParams(message=message)
    # request = SendMessageRequest(id=str(uuid4()), params=params)

    # response = await client.send_message(request)
    # print("Agent Response:")
    # print(response)

if __name__ == "__main__":
    asyncio.run(main())
