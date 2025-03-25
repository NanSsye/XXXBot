import importlib
import inspect
import os
import sys
import tomllib
import traceback
from typing import Dict, Type, List, Union

from loguru import logger

from WechatAPI import WechatAPIClient
from .event_manager import EventManager
from .plugin_base import PluginBase


class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, PluginBase] = {}
        self.plugin_classes: Dict[str, Type[PluginBase]] = {}
        self.plugin_info: Dict[str, dict] = {}  # 新增：存储所有插件信息

        with open("main_config.toml", "rb") as f:
            main_config = tomllib.load(f)

        self.excluded_plugins = main_config["XYBot"]["disabled-plugins"]

    async def load_plugin(self, bot: WechatAPIClient, plugin_class: Type[PluginBase],
                          is_disabled: bool = False) -> bool:
        """加载单个插件，接受Type[PluginBase]"""
        try:
            plugin_name = plugin_class.__name__

            # 防止重复加载插件
            if plugin_name in self.plugins:
                return False

            # 记录插件信息，即使插件被禁用也会记录
            self.plugin_info[plugin_name] = {
                "name": plugin_name,
                "description": plugin_class.description,
                "author": plugin_class.author,
                "version": plugin_class.version,
                "enabled": False,
                "class": plugin_class
            }

            # 如果插件被禁用则不加载
            if is_disabled:
                return False

            plugin = plugin_class()
            EventManager.bind_instance(plugin)
            await plugin.on_enable(bot)
            await plugin.async_init()
            self.plugins[plugin_name] = plugin
            self.plugin_classes[plugin_name] = plugin_class
            self.plugin_info[plugin_name]["enabled"] = True
            return True
        except:
            logger.error(f"加载插件时发生错误: {traceback.format_exc()}")
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """卸载单个插件"""
        if plugin_name not in self.plugins:
            return False

        # 防止卸载 ManagePlugin
        if plugin_name == "ManagePlugin":
            logger.warning("ManagePlugin 不能被卸载")
            return False

        try:
            plugin = self.plugins[plugin_name]
            await plugin.on_disable()
            EventManager.unbind_instance(plugin)
            del self.plugins[plugin_name]
            del self.plugin_classes[plugin_name]
            if plugin_name in self.plugin_info.keys():
                self.plugin_info[plugin_name]["enabled"] = False
            return True
        except:
            logger.error(f"卸载插件 {plugin_name} 时发生错误: {traceback.format_exc()}")
            return False

    async def load_plugins_from_directory(self, bot: WechatAPIClient, load_disabled_plugin: bool = True) -> Union[
        List[str], bool]:
        """从plugins目录批量加载插件"""
        loaded_plugins = []

        for dirname in os.listdir("plugins"):
            if os.path.isdir(f"plugins/{dirname}") and os.path.exists(f"plugins/{dirname}/main.py"):
                try:
                    module = importlib.import_module(f"plugins.{dirname}.main")
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
                            is_disabled = False
                            if not load_disabled_plugin:
                                is_disabled = obj.__name__ in self.excluded_plugins

                            if await self.load_plugin(bot, obj, is_disabled=is_disabled):
                                loaded_plugins.append(obj.__name__)

                except:
                    logger.error(f"加载 {dirname} 时发生错误: {traceback.format_exc()}")
                    return False

        return loaded_plugins

    async def load_plugin_from_directory(self, bot: WechatAPIClient, plugin_name: str) -> bool:
        """从plugins目录加载单个插件

        Args:
            bot: 机器人实例
            plugin_name: 插件类名称（不是文件名）

        Returns:
            bool: 是否成功加载插件
        """
        found = False
        for dirname in os.listdir("plugins"):
            try:
                if os.path.isdir(f"plugins/{dirname}") and os.path.exists(f"plugins/{dirname}/main.py"):
                    module = importlib.import_module(f"plugins.{dirname}.main")
                    importlib.reload(module)

                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and
                                issubclass(obj, PluginBase) and
                                obj != PluginBase and
                                obj.__name__ == plugin_name):
                            found = True
                            return await self.load_plugin(bot, obj)
            except:
                logger.error(f"检查 {dirname} 时发生错误: {traceback.format_exc()}")
                continue

        if not found:
            logger.warning(f"未找到插件类 {plugin_name}")
            return False


    async def unload_all_plugins(self) -> tuple[List[str], List[str]]:
        """卸载所有插件"""
        unloaded_plugins = []
        failed_unloads = []
        for plugin_name in list(self.plugins.keys()):
            if await self.unload_plugin(plugin_name):
                unloaded_plugins.append(plugin_name)
            else:
                failed_unloads.append(plugin_name)
        return unloaded_plugins, failed_unloads

    async def reload_plugin(self, bot: WechatAPIClient, plugin_name: str) -> bool:
        """重载单个插件"""
        if plugin_name not in self.plugin_classes:
            return False

        # 防止重载 ManagePlugin
        if plugin_name == "ManagePlugin":
            logger.warning("ManagePlugin 不能被重载")
            return False

        try:
            # 获取插件类所在的模块
            plugin_class = self.plugin_classes[plugin_name]
            module_name = plugin_class.__module__

            # 先卸载插件
            if not await self.unload_plugin(plugin_name):
                return False

            # 重新导入模块
            module = importlib.import_module(module_name)
            importlib.reload(module)

            # 从重新加载的模块中获取插件类
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                        issubclass(obj, PluginBase) and
                        obj != PluginBase and
                        obj.__name__ == plugin_name):
                    # 使用新的插件类而不是旧的
                    return await self.load_plugin(bot, obj)

            return False
        except Exception as e:
            logger.error(f"重载插件 {plugin_name} 时发生错误: {e}")
            return False

    async def reload_all_plugins(self, bot: WechatAPIClient) -> List[str]:
        """重载所有插件
        
        Returns:
            List[str]: 成功重载的插件名称列表
        """
        try:
            # 记录当前加载的插件名称，排除 ManagePlugin
            original_plugins = [name for name in self.plugins.keys() if name != "ManagePlugin"]

            # 卸载除 ManagePlugin 外的所有插件
            for plugin_name in original_plugins:
                await self.unload_plugin(plugin_name)

            # 重新加载所有模块
            for module_name in list(sys.modules.keys()):
                if module_name.startswith('plugins.') and not module_name.endswith('ManagePlugin'):
                    del sys.modules[module_name]

            # 从目录重新加载插件
            return await self.load_plugins_from_directory(bot)

        except:
            logger.error(f"重载所有插件时发生错误: {traceback.format_exc()}")
            return []

    def get_plugin_info(self, plugin_name: str = None) -> Union[dict, List[dict]]:
        """获取插件信息
        
        Args:
            plugin_name: 插件名称，如果为None则返回所有插件信息
            
        Returns:
            如果指定插件名，返回单个插件信息字典；否则返回所有插件信息列表
        """
        # 创建一个可以JSON序列化的信息副本
        def clean_plugin_info(info):
            result = {
                "id": info.get("name", "unknown"),
                "name": info.get("name", "unknown"),
                "description": info.get("description", ""),
                "author": info.get("author", ""),
                "version": info.get("version", "1.0.0"),
                "enabled": info.get("enabled", False)
            }
            return result
            
        if plugin_name:
            info = self.plugin_info.get(plugin_name)
            if info:
                return clean_plugin_info(info)
            return None
        
        return [clean_plugin_info(info) for info in self.plugin_info.values()]


plugin_manager = PluginManager()
