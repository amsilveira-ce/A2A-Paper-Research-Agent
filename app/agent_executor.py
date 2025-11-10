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

    def execute(self, context, event_queue):
        pass 
    def cancel(self, context, event_queue):
        pass 