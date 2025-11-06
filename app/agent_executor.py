"""
Agent Executor for Paper Research Agent

"""
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from agent import PaperResearchAgent
from a2a.utils.errors import ServerError
from a2a.types import (
    InternalError,
    InvalidParamsError,
    Part,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
import logging
from a2a.utils import (
    new_agent_text_message,
    new_task,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PaperAgentExecutor(AgentExecutor):
    '''
    Paper Research AgentExecutor following official A2A SDK pattern

    → RequestContext for request handling
    → EventQueue for event management
    → TaskUpdater for task state management

    '''

    def __init__(self):
        """Initialize the executor with the paper research agent"""
        self.agent = PaperResearchAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        
        # Check if there is any error in the request made 
        error = self._validate_request(context)
        if error:
            raise ServerError(error=InvalidParamsError())
        
        
        query = context.get_user_input()

        # Get or create task
        task = context.current_task
        if not task:
            task = new_task(context.message)  # type: ignore
            await event_queue.enqueue_event(task)
        



        # Create task updater for state management
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            for event in self.agent.stream(query=query, thread_id=task.context_id):
                if "messages" not in event:
                    continue # we dont have a full message to load 

                last_message = event["messages"][-1]


                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(
                            "Searching arXiv for papers...",
                            task.context_id,
                            task.id,
                        ),
                    )

                # Check if this is final content
                elif hasattr(last_message, "content") and last_message.content:
                    content = last_message.content
                    
                    # Check if more input is needed (shouldn't happen but handle it)
                    if "clarification" in content.lower() or "more information" in content.lower():
                        await updater.update_status(
                            TaskState.input_required,
                            new_agent_text_message(
                                content,
                                task.context_id,
                                task.id,
                            ),
                            final=True,
                        )
                        break
                    
                    # Task is complete - add artifact and complete
                    await updater.add_artifact(
                        [Part(root=TextPart(text=content))],
                        name='paper_search_results',
                    )
                    await updater.complete()
                    break

        except Exception as e:
            logger.error(f'An error occurred while processing the request: {e}')
            raise ServerError(error=InternalError()) from e
        