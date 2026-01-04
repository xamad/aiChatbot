"""服务端插件工具执行器"""

from typing import Dict, Any
from ..base import ToolType, ToolDefinition, ToolExecutor
from plugins_func.register import all_function_registry, Action, ActionResponse
from config.logger import setup_logging

TAG = __name__
logger = setup_logging()


def stop_radio_if_playing(conn):
    """Ferma la radio se sta suonando (per transizione fluida tra funzioni)"""
    try:
        from plugins_func.functions.radio_italia import is_radio_playing, stop_radio
        if is_radio_playing(conn):
            stop_radio(conn)
            logger.bind(tag=TAG).info("Radio fermata automaticamente per cambio funzione")
    except Exception as e:
        logger.bind(tag=TAG).debug(f"Radio stop check: {e}")


def track_function_usage(conn, tool_name: str):
    """Registra l'uso della funzione nella memoria utente"""
    try:
        from plugins_func.functions.user_memory import registra_uso_funzione
        device_id = getattr(conn, 'device_id', None)
        if device_id:
            registra_uso_funzione(device_id, tool_name)
    except Exception as e:
        logger.bind(tag=TAG).debug(f"Memory tracking: {e}")


class ServerPluginExecutor(ToolExecutor):
    """服务端插件工具执行器"""

    def __init__(self, conn):
        self.conn = conn
        self.config = conn.config

    async def execute(
        self, conn, tool_name: str, arguments: Dict[str, Any]
    ) -> ActionResponse:
        """执行服务端插件工具"""
        func_item = all_function_registry.get(tool_name)
        if not func_item:
            return ActionResponse(
                action=Action.NOTFOUND, response=f"插件函数 {tool_name} 不存在"
            )

        # Ferma radio automaticamente se si chiama un'altra funzione
        # (escluso radio_italia stessa)
        if tool_name != "radio_italia":
            stop_radio_if_playing(conn)

        try:
            # 根据工具类型决定如何调用
            if hasattr(func_item, "type"):
                func_type = func_item.type
                if func_type.code in [4, 5]:  # SYSTEM_CTL, IOT_CTL (需要conn参数)
                    result = func_item.func(conn, **arguments)
                elif func_type.code == 2:  # WAIT
                    result = func_item.func(conn, **arguments)
                elif func_type.code == 3:  # CHANGE_SYS_PROMPT
                    result = func_item.func(conn, **arguments)
                else:
                    result = func_item.func(**arguments)
            else:
                # 默认不传conn参数
                result = func_item.func(**arguments)

            # Registra uso funzione nella memoria utente
            track_function_usage(conn, tool_name)

            return result

        except Exception as e:
            return ActionResponse(
                action=Action.ERROR,
                response=str(e),
            )

    def get_tools(self) -> Dict[str, ToolDefinition]:
        """获取所有注册的服务端插件工具"""
        tools = {}

        # 获取必要的函数 (CORE sempre attive)
        necessary_functions = [
            "handle_exit_intent", "get_lunar",
            # AI e risposta
            "risposta_ai", "web_search",
            # Sistema
            "sommario_funzioni", "cambia_profilo", "aiuto_profilo",
            # Easter egg e personalità
            "personalita_multiple", "easter_egg_folli", "giannino_easter_egg",
            # Utility base
            "meteo_italia", "timer_sveglia", "calcolatrice",
            # Media
            "radio_italia", "notizie_italia",
        ]

        # 获取配置中的函数
        config_functions = self.config["Intent"][
            self.config["selected_module"]["Intent"]
        ].get("functions", [])

        # 转换为列表
        if not isinstance(config_functions, list):
            try:
                config_functions = list(config_functions)
            except TypeError:
                config_functions = []

        # 合并所有需要的函数
        all_required_functions = list(set(necessary_functions + config_functions))

        for func_name in all_required_functions:
            func_item = all_function_registry.get(func_name)
            if func_item:
                # 从函数注册中获取描述
                fun_description = (
                    self.config.get("plugins", {})
                    .get(func_name, {})
                    .get("description", "")
                )
                if fun_description is not None and len(fun_description) > 0:
                    if "function" in func_item.description and isinstance(
                        func_item.description["function"], dict
                    ):
                        func_item.description["function"][
                            "description"
                        ] = fun_description
                tools[func_name] = ToolDefinition(
                    name=func_name,
                    description=func_item.description,
                    tool_type=ToolType.SERVER_PLUGIN,
                )

        return tools

    def has_tool(self, tool_name: str) -> bool:
        """检查是否有指定的服务端插件工具"""
        return tool_name in all_function_registry
