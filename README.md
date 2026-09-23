# 本地助手（个人 PoC）

这是一个由 Siri App Shortcut 唤起的 iOS 地图助手原型。用户说“嘿 Siri，问本地助手”，由 Siri 询问具体需求。首个连接器使用高德 Web API 查附近地点、规划路线，再通过高德官方 iOS URI 把路线交给高德 App。打车请求只提供估价和交接，不会创建订单。

## 已实现的边界

- 网关：FastAPI、五种模型协议配置、高德周边搜索/路线、中文规则解析、Mac Keychain 读密钥、设备令牌校验。
- iOS：SwiftUI 文本入口、精确定位、网关连接设置、Siri App Intent、结果卡片和高德 URI。
- 连接器：`manifest.json` 和 action JSON 记录能力、风险和输入结构；复杂执行由审核后的 Python adapter 承担。新连接器需要注册 adapter 才能执行，不能仅靠填 URL 获得任何第三方权限。

当前没有项目真实 API Key、完整 Xcode 或 iPhone 真机验证结果。默认模型 ID 只是可编辑配置，首次使用前应以自己的账号在厂商控制台确认可用模型。

## 网关准备

需要 Python 3.11+、`uv`、macOS Keychain 和高德 Web 服务 Key。先在 `gateway/` 运行：

```sh
uv sync --extra test
uv run python -m assistant.setup amap
uv run python -m assistant.setup device_token
uv run python -m assistant.setup deepseek
uv run uvicorn assistant.api:app --host 127.0.0.1 --port 8765
```

其余模型用 `openai`、`anthropic`、`glm`、`kimi` 分别执行一次 `assistant.setup`。命令会隐藏模型 Key 的输入；生成的设备令牌只显示一次，需复制到 iPhone 的“连接设置”。不要把任何 Key 写进仓库。

网关只监听 Mac 的 loopback。外出访问应通过用户自己配置的受认证 HTTPS 隧道或 VPN 转发到这个端口，不要直接公开 `8765`。iPhone 设置中的网关 URL 必须是 `https://...`。首次使用需先在前台授予位置和局域网权限；Mac 必须保持在线。

## iOS 准备

当前仓库提供 SwiftUI 源码和 XcodeGen 的 `ios/project.yml`。安装完整 Xcode 与 XcodeGen 后，在 `ios/` 运行 `xcodegen generate`，用 Xcode 打开生成的项目，修改 bundle ID 和签名团队，再安装到 iOS 18+ 真机。仅有免费 Apple ID 时，真机签名和安装有效期可能受限。

先在 App 的设置页填写 HTTPS 网关地址与设备令牌，选择默认模型。然后试以下输入：

1. `用高德导航导航到最近的星巴克`
2. `帮我导航到最近的星巴克`
3. `帮我找出附近三公里内评分最高的星巴克`
4. `最近的地铁站该怎么走`
5. `步行到最近的星巴克要多久`

高德未安装时，App 应提示安装；不会切换到 Apple 地图。Siri 的具体口令识别、App Intent 卡片交互和高德 URI 必须以真机结果为准。

## 测试

```sh
cd gateway
uv run pytest -q
```

测试使用假响应，不产生真实 API 费用。真实冒烟测试需要自行提供五家模型 Key、高德 Key、真机、Xcode 和安全的 Mac 访问通道。

## 官方资料

- [Apple App Intents](https://developer.apple.com/documentation/appintents/appintent)
- [Apple App Shortcut 参数](https://developer.apple.com/documentation/appintents/adding-parameters-to-an-app-intent)
- [高德 POI v3](https://lbs.amap.com/api/webservice/guide/api/search/)
- [高德路径规划 2.0](https://lbs.amap.com/api/webservice/guide/api/newroute)
- [高德 iOS 路线 URI](https://lbs.amap.com/api/amap-mobile/guide/ios/route)
- [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)
- [DeepSeek Tool Calls](https://api-docs.deepseek.com/guides/tool_calls/)
- [Anthropic Tool Use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
