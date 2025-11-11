
import asyncio
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from a2a.server.agent_execution import RequestContext  
from a2a.server.events import EventQueue
from a2a.types import  InternalError, InvalidParamsError
from a2a.utils.errors import ServerError
from agent_executor import PaperAgentExecutor  

# To change the logging information just change this values 
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("A2AServer")

app = FastAPI(title="Paper Research Agent – A2A")

executor = PaperAgentExecutor()


# Serve agent card at both /agent-card and /.well-known/agent.json
@app.get("/.well-known/agent.json")
async def agent_card_wellknown():
    try:
        card = executor.get_agent_card()
        return JSONResponse(content=card)
    
    except Exception as e:
        logger.error(f"Error generating agent card: {e}")
        # The ServerError is a wrapper for A2A/JSON-RCP errors from server logic 
        raise ServerError(error=InternalError())

@app.get("/agent-card")
async def agent_card():
    return await agent_card_wellknown()

@app.post("/a2a/{assistant_id}")
async def handle_a2a_request(assistant_id: str, request: Request):
    try:
        body = await request.json()
        jsonrpc = body.get("jsonrpc", "2.0")
        request_id = body.get("id", "")
        method = body.get("method", "")
        params = body.get("params", {})

        logger.info(f"Received method {method} for assistant_id {assistant_id}")

        if method in ("message/send", "tasks/send"):
            return await handle_send(request_id, params, jsonrpc)
        elif method == "message/stream":
            return await handle_stream(request_id, params, jsonrpc)
        else:
            error = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            return JSONResponse(content=error, status_code=404)

    except Exception as e:
        logger.exception("Unhandled exception in /a2a")
        error = {
            "jsonrpc": "2.0",
            "id": "",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return JSONResponse(content=error, status_code=500)

async def handle_send(request_id: str, params: dict, jsonrpc: str):
    try:
        context = RequestContext.from_a2a(params)
        event_queue = EventQueue()

        await executor.execute(context, event_queue)

        # gather all events
        events = event_queue.get_all_events()
        # convert to JSON-friendly
        events_data = [e.model_dump(mode="json", exclude_none=True) for e in events]

        response = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "result": {
                "events": events_data,
                "status": "completed"
            }
        }
        return JSONResponse(content=response)

    except InvalidParamsError as e:
        error = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "error": {
                "code": -32602,
                "message": str(e)
            }
        }
        return JSONResponse(content=error, status_code=400)

    except Exception as e:
        logger.error(f"Error in handle_send: {e}")
        error = {
            "jsonrpc": jsonrpc,
            "id": request_id,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }
        return JSONResponse(content=error, status_code=500)

async def handle_stream(request_id: str, params: dict, jsonrpc: str):
    context = RequestContext.from_a2a(params)
    event_queue = EventQueue()

    # launch executor in background
    asyncio.create_task(executor.execute(context, event_queue))

    async def event_generator():
        try:
            while True:
                event = await event_queue.dequeue_event()
                if event is None:
                    break
                data = {
                    "jsonrpc": jsonrpc,
                    "id": request_id,
                    "result": event.model_dump(mode="json", exclude_none=True)
                }
                yield f"data: {json.dumps(data)}\n\n"

                # if this event signals completion, stop
                if event.type == "completion":
                    break

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            error = {
                "jsonrpc": jsonrpc,
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Stream error: {str(e)}"
                }
            }
            yield f"data: {json.dumps(error)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "paper-research"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting A2A Server on http://0.0.0.0:10000")
    uvicorn.run(app, host="0.0.0.0", port=10000)