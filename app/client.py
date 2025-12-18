import asyncio
from a2a.client import ClientFactory
from uuid import uuid4

async def main():
    base_url = "http://localhost:10000/a2a"

    # Create client via factory
    client = ClientFactory.create(base_url)

    # Discover the agent
    card = await client.get_agent_card()
    print("Discovered agent:")
    print(card)

    # Example for later:
    # message = Message(role="user", parts=[MessagePart(kind="text", text="Find papers on quantum computing")])
    # params = MessageSendParams(message=message)
    # request = SendMessageRequest(id=str(uuid4()), params=params)
    # response = await client.send_message(request)
    # print(response)

if __name__ == "__main__":
    asyncio.run(main())
