import copy
from typing import Callable, Dict, List


class EventManager:
    _handlers: Dict[str, List[tuple[Callable, object, int]]] = {}

    @classmethod
    def bind_instance(cls, instance: object):
        """将实例绑定到对应的事件处理函数"""
        for method_name in dir(instance):
            method = getattr(instance, method_name)
            if hasattr(method, '_event_type'):
                event_type = getattr(method, '_event_type')
                priority = getattr(method, '_priority', 50)
                
                if event_type not in cls._handlers:
                    cls._handlers[event_type] = []
                cls._handlers[event_type].append((method, instance, priority))
                # 按优先级排序，优先级高的在前
                cls._handlers[event_type].sort(key=lambda x: x[2], reverse=True)

    @classmethod
    async def emit(cls, event_type: str, *args, **kwargs) -> None:
        """触发事件"""
        if event_type not in cls._handlers:
            return

        api_client, message = args
        for handler, instance, priority in cls._handlers[event_type]:
            # 只对 message 进行深拷贝，api_client 保持不变
            handler_args = (api_client, copy.deepcopy(message))
            new_kwargs = {k: copy.deepcopy(v) for k, v in kwargs.items()}

            result = await handler(*handler_args, **new_kwargs)

            if isinstance(result, bool):
                # True 继续执行 False 停止执行
                if not result:
                    break
            else:
                continue  # 我也不知道你返回了个啥玩意，反正继续执行就是了

    @classmethod
    def unbind_instance(cls, instance: object):
        """解绑实例的所有事件处理函数"""
        for event_type in cls._handlers:
            cls._handlers[event_type] = [
                (handler, inst, priority)
                for handler, inst, priority in cls._handlers[event_type]
                if inst is not instance
            ]
