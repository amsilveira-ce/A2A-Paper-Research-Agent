# Agent logic 
# Code with a agent and custom tool implementation

import subprocess
import sys
from typing import TypedDict, Annotated, List, Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import MessagesState, END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from typing import Any, Literal

# Using ollama to call the model that will work as the brain of the agent
llama = ChatOllama(
    model="llama3.1:8b",
    temperature=0.7,
)


@tool
def search_arXiv(query: str, max_results: int = 5) -> str:
    """
    Search arXiv for academic papers related to a given query.

    Args:
        query (str): The topic or keywords to search for.
        max_results (int): Maximum number of papers to retrieve.

    Returns:
        str: A formatted string containing metadata of the retrieved papers.
    """
    try:
        import arxiv
    except ModuleNotFoundError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "arxiv"])
        import arxiv

    if not query or not isinstance(query, str):
        raise ValueError(f"Query must be a non-empty string. Found value: {query}")
    if not isinstance(max_results, int):
        raise ValueError(f"max_results must be an integer. Found value: {max_results}")

    try:
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )

        results = list(search.results())
        if not results:
            return "No papers found related to the search query."

        paper_details = []
        for i, result in enumerate(results):
            summary = result.summary.replace('\n', ' ')
            authors = ", ".join(author.name for author in result.authors)
            paper_details.append(
                f"Paper {i+1}:\n"
                f"  Title: {result.title}\n"
                f"  Authors: {authors}\n"
                f"  URL: {result.entry_id}\n"
                f"  Abstract: {summary}...\n"
            )

        return "\n".join(paper_details)

    except Exception as e:
        return f"An error occurred while searching arXiv: {str(e)}"

class ResponseFormat(BaseModel):
    status: Literal['input_required', 'completed','error'] = 'input_required'
    message: str 


class PaperResearchAgent():
    """
    A2A-compatible Paper Research Agent using LangGraph ReAct pattern
    """

    system_prompt = """
    You are a **research assistant specialized in academic paper retrieval**.

    ## Role:
    - You help users find, summarize, and organize academic papers on requested topics.
    - You must **only** use your available tools (e.g., paper retriever, API, or database) to access and return paper information.
    - You are **not allowed** to fabricate or invent any data, citations, or internal details that are not explicitly retrieved from your tools.
    - You may ask the user for clarification if the request is ambiguous or incomplete.

    ## Behavior Guidelines:
    1. Always verify that the query is clear enough before using tools.
    2. Keep responses factual and concise unless the user asks for detailed summaries.
    3. If no relevant papers are found, inform the user and suggest how they can refine their query.
    4. Avoid assumptions — rely strictly on the data returned by your tools.
    5. If tool access fails, respond with an error and do not make up results.

    ## Response Structure:
    - **status**: one of ["input_required", "error", "completed"]
    - **message**: your main response or clarification for the user
    - **data** (optional): structured information such as paper titles, authors, links, summaries

    Example:
    {
    "status": "completed",
    "message": "Here are 3 recent papers about quantum computing optimization.",
    "data": [
        {"title": "Variational Quantum Algorithms Review", "authors": ["John Doe"], "year": 2023, "link": "https://arxiv.org/..."},
        {"title": "Quantum Annealing for Combinatorial Problems", "authors": ["Jane Smith"], "year": 2022, "link": "https://arxiv.org/..."}
    ]
    }
    """
    format_instruction = """
        ## Format Instruction:
        - Set response status to **input_required** if more info from user is needed.
        - Set response status to **error** if there is an error during tool access or parsing.
        - Set response status to **completed** if the request was processed successfully.
    """

    def __init__(self): 

        self.tools = [search_arXiv]
        self.llm_with_tools = llama.bind_tools(self.tools)
        self.memory = MemorySaver() # 
        self.graph = self._build_graph()
        print(self.graph)

    
    def _build_graph(self) -> StateGraph:
        """Builds the LangGraph state graph."""

        def call_model(state: MessagesState) -> dict[str, Any]:
            """Node: calls the LLM"""
            messages = state["messages"]
            # Add system prompt on first message
            if not any(isinstance(m, SystemMessage) for m in messages):
                messages = [SystemMessage(content=self.system_prompt)] + messages
            response = self.llm_with_tools.invoke(messages)
            return {"messages": [response]}

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(self.tools))

        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", tools_condition)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("agent", END)

        return workflow.compile(checkpointer=self.memory)

    def invoke(self, query: str, thread_id: str="default") -> dict[str,Any]:
        # Use the thread_id for conversation persistence 
        config = {'configurable': {'thread_id': thread_id}}

        result = self.graph.invoke(
            {
                "messages": [("user", query)]
            },
            config 
        )

        return result 
    
    def stream(self, query: str, thread_id: str = "default"):
        ''''''
        config = {"configurable": {"thread_id": thread_id}}

        for event in self.graph.stream(
            {"messages": [("user", query)]},
            config,
            stream_mode="values"
        ):
            yield event

if __name__ == "__main__":
    # Run this file to teste how the Paper Research Agent works and test new integrations
    agent = PaperResearchAgent()

    debug_mode = input("Do you want stream mode? type yes or not: ")

   
    if debug_mode=="yes":
        print("Streaming response:\n")   
        for event in agent.stream(query="Find recent papers on diffusion models"):       
            print(event)
    else:
        # Print the last message
        result = agent.invoke(query="Find recent papers on transformer models")
        if result and "messages" in result:
            last_message = result["messages"][-1]
            print(f"Agent response: {last_message.content}")