# Import all tools so they self-register via decorators
from tools.search_tool import web_search
from tools.workspace_tool import write_file, read_file, list_workspace
from tools.code_runner_tool import run_code
from tools.memory_tool import memory_recall, memory_write
from tools.base import TOOL_REGISTRY, get_tool_schemas, execute_tool
