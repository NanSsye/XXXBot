# OpenManus 智能代理插件

OpenManus 是一个增强型智能代理插件，基于 Gemini 大型语言模型实现多步骤思考和工具使用，为微信机器人提供强大的智能助手功能，支持上下文对话和语音回复。

**作者：老夏的金库**

## 功能特点

- **多步骤思考**: 使用 MCP (多步认知过程) 方法进行复杂问题分析
- **工具集成**: 支持多种工具调用，包括计算器、日期时间、搜索等
- **语音合成**: 支持 Fish Audio 和 MiniMax T2A v2 双引擎语音合成
- **图像生成**: 支持 ModelScope 文本生成图像功能
- **丰富交互**: 支持私聊和群聊，可通过触发词或@方式激活
- **灵活配置**: 支持多种配置选项，包括模型选择、语音参数、工具启用等
  **股票工具**: 查询股票数据

## 安装方法

1. 确保已安装必要的依赖:

   ```
   pip install -r requirements.txt
   ```

2. 将 OpenManus 插件目录放置在机器人的 plugins 目录下
3. 编辑配置文件 `config.toml`，设置你的 API 密钥和其他选项
4. 重启机器人服务

## 配置说明

配置文件位于 `plugins/OpenManus/config.toml`，主要配置项如下:

````toml
[basic]
# 插件基本配置
enable = true                 # 是否启用插件
trigger_keyword = "agent"     # 触发词，用于命令识别
allow_private_chat = true     # 是否允许私聊使用
respond_to_at = true          # 是否允许群里@使用

[gemini]
# Gemini API配置
api_key = ""                  # Gemini API密钥
base_url = "https://generativelanguage.googleapis.com/v1beta"  # API基础URL
use_sdk = true                # 是否使用官方SDK（必须为true才能启用上下文对话）

[agent]
# 代理配置
default_model = "gemini-2.0-flash"  # 默认使用的模型
max_tokens = 8192             # 最大生成token数
temperature = 0.7             # 温度参数(0-2)
max_steps = 10                # 最大执行步骤数

[mcp]
# MCP配置
enable_mcp = true             # 是否启用MCP思考
thinking_steps = 3            # 思考步骤数

[memory]
# 对话记忆配置
enable_memory = true          # 是否启用记忆功能
max_history = 10              # 最大历史记录条数
separate_context = true       # 是否为不同会话维护单独的上下文

[tools]
# 工具配置
enable_search = true          # 是否启用搜索工具
enable_calculator = true      # 是否启用计算器工具
enable_datetime = true        # 是否启用日期时间工具
enable_weather = true         # 是否启用天气工具
enable_code = true            # 是否启用代码工具
enable_stock = true           # 是否启用股票工具
enable_drawing = true         # 是否启用绘图工具
bing_api_key = ""             # Bing搜索API密钥
serper_api_key = ""           # Serper搜索API密钥
search_engine = "serper"      # 搜索引擎选择(bing或serper)

[drawing]
# 绘图工具配置
api_base = "https://www.modelscope.cn/api/v1/muse/predict"  # ModelScope API基础URL
max_wait_time = 120          # 图像生成最大等待时间(秒)
default_model = "default"    # 默认模型类型：default, anime, realistic
default_ratio = "1:1"        # 默认图像比例：1:1, 4:3, 3:4, 16:9, 9:16
modelscope_cookies = ""      # ModelScope网站Cookie，用于认证
modelscope_csrf_token = ""   # ModelScope网站CSRF令牌

[tts]
# Fish Audio TTS配置
enable = false                # 是否启用Fish Audio TTS
api_key = ""                  # Fish Audio API密钥
reference_id = ""             # 自定义模型ID
format = "mp3"                # 输出格式
mp3_bitrate = 128             # MP3比特率

[minimax_tts]
# MiniMax TTS配置
enable = false                # 是否启用MiniMax TTS
api_key = ""                  # MiniMax API密钥
group_id = ""                 # MiniMax Group ID
model = "speech-02-hd"        # 模型版本
voice_id = "male-qn-qingse"   # 声音ID
format = "mp3"                # 输出格式
sample_rate = 32000           # 采样率
bitrate = 128000              # 比特率
speed = 1.0                   # 语速(0.5-2.0)
vol = 1.0                     # 音量(0.5-2.0)
pitch = 0.0                   # 音调(-1.0-1.0)
emotion = "neutral"           # 情感("happy", "sad", "angry", 等)
language_boost = "auto"       # 语言增强

## 工具列表

以下是默认包含的工具：

1. **计算器工具 (Calculator)**: 进行数学计算
2. **日期时间工具 (DateTime)**: 获取当前日期、时间、计算日期差等
3. **搜索工具 (Search)**: 使用 Bing 或 Serper.dev 搜索网络信息
4. **天气工具 (Weather)**: 获取天气预报信息
5. **代码工具 (Code)**: 执行代码（Python, JavaScript 等）
6. **绘图工具 (Drawing)**: 使用 ModelScope 生成图像
7. **股票工具 (Stock)**: 获取股票实时数据和历史走势
8. **Firecrawl工具**: 爬取网站、搜索网页内容并提取结构化数据

## Firecrawl 工具配置

Firecrawl 工具可以爬取网站、搜索内容并提取结构化数据，特别适合进行信息收集和网站内容分析。该工具支持以下功能：

1. **单页抓取**：获取单个 URL 的内容
2. **多页爬取**：抓取整个网站或网站的特定部分
3. **网页搜索**：结合搜索引擎和网页内容抓取

### 配置方法

在 `config.toml` 文件中添加以下配置：

```toml
[firecrawl]
api_key = "YOUR_FIRECRAWL_API_KEY" # Firecrawl API Key, 请前往 https://firecrawl.dev/ 获取
````

### 使用示例

```
agent 使用 Firecrawl 爬取 https://docs.firecrawl.dev/ 网站内容
```

```
agent 搜索关于量子计算的最新进展并提取结构化数据
```

## 使用方法

### 私聊模式

直接向机器人发送以触发词开头的消息:

```
agent 计算 (5+3)*2
```

### 群聊模式

两种方式:

1. @机器人 并输入问题
2. 以触发词开头:
   ```
   agent 查询最新比特币价格
   ```

### 上下文对话

系统会自动记住对话历史，要清除历史可发送:

```
agent 清除对话
```

或

```
agent 清除记忆
```

## 支持的工具

1. **计算器**: 执行数学计算

   - 用法: `agent 计算 <表达式>`
   - 示例: `agent 计算 sin(0.5)*5+sqrt(16)`

2. **日期时间**: 获取日期时间信息

   - 用法: `agent 日期 [操作]`
   - 示例: `agent 查询两周后是什么日期`

3. **搜索**: 执行网络搜索(需配置 API 密钥)

   - 用法: `agent 搜索 <关键词>`
   - 示例: `agent 搜索 2023年经济增长率`

4. **天气**: 获取天气信息(需配置 API 密钥)

   - 用法: `agent 天气 <城市>`
   - 示例: `agent 查询北京天气`
   - 高级示例: `agent 查询江西南昌的天气状况`
   - API 来源: ALAPI 天气接口，提供全面的天气数据，包括天气状况、温度、湿度、风力、空气质量和生活指数等

5. **代码工具**: 生成和执行代码

   - 用法: `agent 生成代码 <需求>`
   - 示例: `agent 生成一个Python爬虫程序`

6. **股票工具**: 查询股票数据

   - 用法: `agent 查询股票 <股票代码>`
   - 示例: `agent 查询上证指数最近一周走势`

7. **绘图工具**: 根据文本描述生成图像
   - 用法: `agent 绘制 <图像描述>`
   - 示例: `agent 绘制一只可爱的小猫咪`
   - 支持多种风格: 默认风格、动漫风格、写实风格
   - 支持多种图像比例: 1:1、4:3、3:4、16:9、9:16
   - 高级示例: `agent 绘制一个未来科技城市，采用写实风格，比例为16:9`

## 语音合成功能

OpenManus 支持两种语音合成引擎：

1. **Fish Audio TTS**:

   - 基于自定义音色的高质量语音合成
   - 需要配置 API 密钥和 Reference ID
   - 支持 mp3/wav/pcm 格式输出

2. **MiniMax T2A v2**:
   - 支持 100+系统音色和复刻音色
   - 提供情感控制、语速、音量等调整
   - 支持 mp3/pcm/flac/wav 格式输出
   - 可调整采样率、比特率等音频参数

当同时启用两种 TTS 引擎时，系统会优先使用 MiniMax TTS，如果失败则回退到 Fish Audio TTS。

## 图像生成功能

OpenManus 集成了 ModelScope 的图像生成功能，可以根据用户的文本描述生成高质量图像：

1. **基本使用**:

   - 直接发送: `agent 绘制 <图像描述>`
   - 示例: `agent 绘制一片星空下的城市夜景`

2. **风格选择**:

   - 默认风格: 通用画面生成
   - 动漫风格: 适合生成动漫风格的图像
   - 写实风格: 适合生成逼真的照片风格图像

3. **图像比例**:

   - 支持多种比例: 1:1(方形)、4:3(横向)、3:4(纵向)、16:9(宽屏)、9:16(手机屏)
   - 指定比例示例: `agent 绘制一片大海，比例为16:9`

4. **高级提示**:

   - 描述越详细，生成的图像质量越高
   - 建议使用英文描述获得更好效果
   - 可以指定风格、光照、画面构图等细节

5. **使用示例**:
   ```
   agent 绘制一个少女站在花丛中，动漫风格，比例3:4
   ```
   ```
   agent 绘制 a futuristic cityscape with flying cars and neon lights, photorealistic style
   ```

注意：使用绘图功能需要先在 `config.toml` 的 `[drawing]` 部分配置正确的 ModelScope Cookie 和 CSRF Token。

## 股票查询功能

OpenManus 集成了 AKShare 金融数据查询功能，支持查询 A 股、港股和美股的股票数据：

1. **基本使用**:

   - 直接发送: `agent 查询股票 <股票代码>`
   - 示例: `agent 查询股票 600519`（贵州茅台）

2. **支持的市场**:

   - A 股市场: 股票代码前可添加`sh`或`sz`（如`sh600519`或直接`600519`）
   - 港股市场: 股票代码前需添加`hk`（如`hk00700`表示腾讯控股）
   - 美股市场: 股票代码前需添加`us`（如`usAAPL`表示苹果公司）

3. **查询类型**:

   - 基本信息: `agent 查询股票信息 <股票代码>`（获取股票名称、行业、市值等基本信息）
   - 实时行情: `agent 查询股票实时行情 <股票代码>`（获取最新价格、涨跌幅等实时数据）
   - 历史数据: `agent 查询股票历史数据 <股票代码> <开始日期> <结束日期>`（获取指定时间段的历史价格）
   - 综合查询: `agent 分析股票 <股票代码>`（获取综合分析，包括基本面、技术面等）

4. **高级查询示例**:

   ```
   agent 对比分析贵州茅台和五粮液近一个月的股价走势
   ```

   ```
   agent 查询恒生指数今日行情和成分股表现
   ```

   ```
   agent 分析美股特斯拉公司最近一季度财报数据
   ```

5. **技术指标分析**:
   - 支持常见技术指标分析，如 MA（均线）、MACD、KDJ、RSI 等
   - 示例: `agent 分析茅台股票的MACD指标`

注意：股票数据功能依赖于 AKShare 库的数据接口，数据可能会有略微延迟。实时行情数据通常有 15-30 分钟延迟，遵循金融数据使用规范。

## 开发文档

### 项目结构

```
plugins/OpenManus/
├── config.toml         # 配置文件
├── main.py             # 插件入口
├── api_client.py       # API客户端
├── README.md           # 说明文档
├── requirements.txt    # 依赖列表
├── agent/
│   └── mcp.py          # MCP代理实现
└── tools/
    ├── basic_tools.py  # 基础工具实现
    ├── stock_tool.py   # 股票工具实现
    └── drawing_tool.py # 绘图工具实现
```

### 扩展开发

#### 添加新工具

要添加新工具，可以在`tools`目录下创建新的工具类并继承`Tool`基类:

```python
from ..agent.mcp import Tool

class MyNewTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="我的新工具",
            parameters={
                "param1": {
                    "type": "string",
                    "description": "参数1"
                }
            }
        )

    async def execute(self, param1: str) -> Dict[str, Any]:
        # 实现工具功能
        return {"result": f"处理结果: {param1}"}
```

然后在`main.py`的`_create_and_register_agent`方法中注册该工具。

#### 自定义工具开发指南

OpenManus 支持通过工具系统扩展 AI 助手的能力。以下是开发自定义工具的详细流程：

##### 1. 工具基类说明

所有工具必须继承自 `Tool` 基类：

```python
from plugins.OpenManus.agent.mcp import Tool

class MyCustomTool(Tool):
    def __init__(self):
        super().__init__(
            name="my_custom_tool",      # 工具名称，必须唯一
            description="这个工具用于实现某项特定功能",  # 工具说明，AI将根据此决定何时使用工具
            parameters={                # 参数定义，遵循JSON Schema规范
                "param1": {
                    "type": "string",
                    "description": "参数1的说明"
                },
                "param2": {
                    "type": "integer",
                    "description": "参数2的说明",
                    "default": 10       # 包含default表示此参数可选
                }
            },
            required=["param1"]         # 必填参数列表（可选，若不提供则自动根据是否有default判断）
        )

    async def execute(self, **kwargs):
        """实现工具逻辑，必须是异步方法"""
        # 获取参数
        param1 = kwargs.get("param1")
        param2 = kwargs.get("param2", 10)

        # 执行操作
        result = await self._do_something(param1, param2)

        # 返回结果（必须是字典格式）
        return {
            "result": result,
            "status": "success"
        }

    async def _do_something(self, param1, param2):
        """实现具体功能的辅助方法"""
        # 具体实现...
        return f"处理结果: {param1}, {param2}"
```

##### 2. 参数类型支持

参数定义支持以下类型：

- `string`：字符串
- `integer`：整数
- `number`：浮点数
- `boolean`：布尔值
- `array`：数组，可通过 `items` 定义元素类型
- `object`：对象，可通过 `properties` 定义属性

示例：

```python
parameters={
    "text": {
        "type": "string",
        "description": "要处理的文本"
    },
    "options": {
        "type": "array",
        "items": {"type": "string"},
        "description": "处理选项列表"
    },
    "config": {
        "type": "object",
        "properties": {
            "mode": {"type": "string"},
            "level": {"type": "integer"}
        },
        "description": "配置对象"
    }
}
```

##### 3. 配置集成

为使工具可配置，建议遵循以下步骤：

1. 在 `config.toml` 中添加工具配置：

```toml
[tools]
# 现有配置...
enable_my_custom_tool = true  # 是否启用自定义工具

[my_custom_tool]
# 工具特定配置
api_key = ""  # 如果需要API密钥
base_url = ""  # 如果需要API地址
timeout = 30   # 其他配置参数
```

2. 在 `main.py` 的 `__init__` 方法中读取配置：

```python
def __init__(self, config_path: str = "plugins/OpenManus/config.toml"):
    # ... 现有代码 ...

    # 读取自定义工具配置
    custom_tool_config = self.config.get("my_custom_tool", {})
    self.enable_my_custom_tool = tools_config.get("enable_my_custom_tool", False)
    self.custom_tool_api_key = custom_tool_config.get("api_key", "")
    self.custom_tool_base_url = custom_tool_config.get("base_url", "")
    self.custom_tool_timeout = custom_tool_config.get("timeout", 30)
```

3. 在 `_create_and_register_agent` 方法中注册工具：

```python
def _create_and_register_agent(self):
    # ... 现有代码 ...

    # 添加自定义工具
    if self.enable_my_custom_tool and self.custom_tool_api_key:
        tools.append(MyCustomTool(
            api_key=self.custom_tool_api_key,
            base_url=self.custom_tool_base_url,
            timeout=self.custom_tool_timeout
        ))
```

##### 4. 实现工具功能

在 `execute` 方法中实现工具核心功能：

1. **API 调用工具**：

```python
async def execute(self, **kwargs):
    """执行API调用"""
    query = kwargs.get("query")

    # 构建API请求
    headers = {"Authorization": f"Bearer {self.api_key}"}
    params = {"q": query}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/search",
                headers=headers,
                params=params,
                timeout=self.timeout
            ) as response:

                if response.status != 200:
                    return {"error": f"API返回错误: {response.status}"}

                data = await response.json()
                return {"results": data.get("results", [])}

    except Exception as e:
        return {"error": f"API调用失败: {str(e)}"}
```

2. **本地处理工具**：

```python
async def execute(self, **kwargs):
    """本地数据处理"""
    text = kwargs.get("text")
    mode = kwargs.get("mode", "default")

    # 根据模式执行不同处理
    if mode == "analyze":
        result = self._analyze_text(text)
    elif mode == "transform":
        result = self._transform_text(text)
    else:
        result = text

    return {"processed_text": result}
```

##### 5. 错误处理

工具应当妥善处理异常，避免整个系统因工具错误而崩溃：

```python
async def execute(self, **kwargs):
    try:
        # 工具逻辑...
        return {"result": result}
    except ValueError as ve:
        # 参数错误
        return {"error": f"参数错误: {str(ve)}"}
    except aiohttp.ClientError as ce:
        # 网络错误
        return {"error": f"API连接错误: {str(ce)}"}
    except Exception as e:
        # 其他错误
        return {"error": f"工具执行异常: {str(e)}"}
```

##### 6. 工具开发最佳实践

1. **清晰的描述**：提供准确的工具描述和参数说明，帮助 AI 正确选择和使用工具
2. **必要的验证**：在工具执行前验证参数的有效性
3. **合理的超时**：为网络请求设置适当的超时时间
4. **详细的日志**：记录工具执行的关键步骤和结果
5. **优雅的失败**：即使出错也返回有用的错误信息，而非抛出异常
6. **可配置性**：通过配置文件使工具行为可调整
7. **测试**：编写单元测试确保工具在各种情况下正常工作

##### 7. 工具类型示例

常见工具类型及示例：

1. **搜索工具**：从网络搜索信息
2. **翻译工具**：调用翻译 API 进行语言转换
3. **数据库工具**：查询本地数据库
4. **文档处理工具**：分析、生成或修改文档
5. **媒体处理工具**：处理图像、音频或视频
6. **IoT 控制工具**：与智能家居或其他设备交互
7. **AI 服务集成**：调用其他 AI 服务如图像识别

通过开发自定义工具，您可以显著扩展 OpenManus 的能力，使其适应各种特定场景和需求。

## 依赖要求

所需的依赖项已在项目根目录的`requirements.txt`文件中列出：

```
# 核心依赖
aiohttp>=3.8.4
tomli>=2.0.1
loguru>=0.6.0
pydub>=0.25.1
aiofiles>=23.1.0

# Gemini SDK（用于上下文对话）
google-generativeai>=0.3.0

# 音频处理依赖
fish-audio-sdk>=1.0.0  # Fish Audio TTS（可选）
requests>=2.28.0       # MiniMax TTS使用

# 工具依赖
python-dateutil>=2.8.2  # 日期时间工具
```

## 常见问题

### API 密钥问题

如果遇到 API 连接问题，请检查:

1. API 密钥是否正确设置
2. 网络连接是否正常
3. API 基础 URL 是否需要修改

对于 ALAPI 天气接口:

1. 需要在[ALAPI 官网](https://alapi.cn)注册账号
2. 创建 API Token 并获取密钥
3. 将密钥填入`config.toml`的`weather_api_key`字段

### 上下文对话问题

如果上下文对话功能不工作，请检查:

1. `gemini.use_sdk`是否设置为`true`
2. 是否已安装 Google Generative AI SDK (`pip install google-generativeai`)
3. `memory.enable_memory`是否设置为`true`

### 语音合成问题

如果语音合成不工作，请检查:

1. 相应 TTS 引擎的`enable`是否设置为`true`
2. API 密钥和其他必要参数是否已正确配置
3. 音频参数是否设置为合理的值

### 绘图功能问题

如果绘图功能不工作，请检查:

1. `tools.enable_drawing`是否设置为`true`
2. ModelScope 的 Cookie 和 CSRF Token 是否已正确设置
3. 获取 Cookie 和 CSRF Token 的方法:
   - 登录 ModelScope 网站 (https://www.modelscope.cn)
   - 打开浏览器开发者工具，找到 Network 标签
   - 刷新页面，找到任意请求
   - 在请求头中找到"Cookie"值和"x-csrf-token"值

### 性能优化

如果遇到响应慢的问题:

1. 减少`thinking_steps`的值
2. 使用更快的模型（如`gemini-2.0-flash`）
3. 减少`max_tokens`值

## 版权和许可

OpenManus 插件使用 MIT 许可证。更多信息请参见 LICENSE 文件。

**作者：老夏的金库**
