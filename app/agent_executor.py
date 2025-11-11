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
from typing import Any
from a2a.utils import (
    new_agent_text_message,
    new_task,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PaperAgentExecutor(AgentExecutor):

    def __init__(self):
        self.agent = PaperResearchAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue):

        error = self._validate_request(context)

        if error:
            raise ServerError(error=InvalidParamsError())
        
        # extract the user input from the context 
        query = context.get_user_input()
        logger.debug("Query extracted from the context: ", query)

        task = context.current_task
        logger.debug("Task extracted from the context: ", task)

        # this does not seems right ???? 
        # why do we enqueue a blank task when we do not find a task on the request 
        # how we guardianrail the agents in this? there is a coner case here? 
        if not task: 
            task = new_task(context.message)
            await event_queue.enqueue_event(task)


        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            for event in self.agent.stream(query, thread_id=task.context_id):
                if "messages" not in event:
                    continue 
                
                # Last message recieved from the stream mode 
                # stream mode is implemented on the agent code 
                last_message = event['messages'][-1]

                # Check if there is a tool calling
                if hasattr(last_message, "tool_calls") and last_message.tool_calls: 
                    await updater.update_status(
                        # the agent is in working mode 
                        TaskState.working,
                        new_agent_text_message(
                            "Searching in arXiv for papers ... ", 
                            task.context_id, 
                            task.id
                        ),
                    )

                # Check if this is the final content 
                elif hasattr(last_message, "content") and last_message.content: 
                    content = last_message.content 

                    if "clarification" in content.lower() or "more information" in content.lower():
                        await updater.update_status(
                            # in this case we are asking the client user for more context - not enought to generate a response 
                            TaskState.input_required,
                            new_agent_text_message(
                                content, 
                                task.context_id,
                                task.id
                            ),
                            final = True 
                        )

                        break 

                    # Task is completed 
                    await updater.add_artifact(
                        [Part(root=TextPart(text=content))],
                        name = 'paper_search_results'
                    )

                    await updater.complete()
                    break 

        except Exception as e:
            logger.error(f'A error occured while processing the request: {e}')
            raise ServerError(error=InternalError()) from e
        
    def _validate_request(self, context: RequestContext)-> bool: 
        """
        Validate the request from the client 

        Args: 
            context: RequestContext to validate 

        Returns:
            bool: True if validation fails, False if valid 
        """

        try: 
            query = context.get_user_input()
            if not query or not query.strip(): 
                logger.error("No user input provided")
                return True 
        except Exception as e: 
            logger.error(f"Error extracting use input: {e}")
            return True 
        
        return False 
    
    def get_agent_card(self)-> dict[str,Any]:
        """
        Get the agent card (Capabilities description)

        Returns:
            dict: Agent Card information
        """
        
        return {
            "name": "Paper Researcher Agent", 
            "description": "Agent specialized in finding and analyzing academic papers from arXiv", 
            "version": "1.0.0", 
            "capabilities": {
                "streaming": True, 
                "mult_turn": True, 
                "tools": [
                    {
                        "name": "search_arxiv", 
                        "description": "Search arXiv for academic papers", 
                        "parameters": {
                            "query": "Search Keys", 
                            "max_results": "Maximum number of papers (default: 5)"
                            }
                    }
                ]
            },
            "skills": [
                {
                    "name": "paper_search",
                    "description": "Search for academic papers on any topic"
                },
                {
                    "name": "paper_analysis",
                    "description": "Analyze and summarize paper information"
                },
                {
                    "name": "recommendation",
                    "description": "Provide relevant paper recommendations"
                }
            ],
            "outputModes": ["text"],
            "inputModes": ["text"]
        }
    def cancel(self, context: RequestContext, event_queue: EventQueue):
        '''
        Cancel a ongoing task 
        Args: 
            context: RequestContext 
            event_queue: EventQueue
        
        Raises 
            ServerError: Always raises UnsupportedOperationError
        '''

        # is this the best way to implement the cancel of a2a? 
        # how do we know if the agent does not support a operation 
        # we do not call cancel in execute 

        # this task is not supported for this agent 
        raise ServerError(error=UnsupportedOperationError())