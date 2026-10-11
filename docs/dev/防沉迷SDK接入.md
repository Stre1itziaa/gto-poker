# 防沉迷 SDK 接入说明（TapTap 合规认证）

**状态**：代码全量就位（v0.2 APK），**默认关闭**——填入 Client ID 即启用。
TapTap 审核对未接防沉迷的棋牌类会卡审核，这是过审的硬前置。

## 一、已施工内容（本机已完成，无需再动）

| 层 | 文件 | 说明 |
|---|---|---|
| 原生桥 | `mobile/android/app/src/main/java/com/yozora/gtopoker/AntiAddictionPlugin.java` | Capacitor 插件：init/startup/exit/getRemainingTime/getAgeRange，SDK 回调→JS `result` 事件 |
| 注册 | `MainActivity.java` | `registerPlugin(AntiAddictionPlugin.class)` |
| 依赖 | `app/build.gradle` | `com.taptap.sdk:tap-core/login/compliance:4.10.9`（mavenCentral） |
| JS 封装 | `js/anti-addiction.js` | 遮罩 UI/重试/游客设备ID（localStorage 稳定 UID）；Web 态自动 no-op |
| 配置 | `js/anti-addiction.js` 顶部 `CONFIG` | **clientId/clientToken 待填** |

TapSDK 规格（官方 guide 逐字核对）：初始化须主线程；`TapTapCompliance.startup(activity, userId)` 的
userId 建议用 TapTap openId，本游戏无账号体系，改用设备随机 UID（≤160 字符，合法字符集内）。

## 二、回调处理矩阵（已实现）

| code | 含义 | 游戏行为 |
|---|---|---|
| 500 | 认证通过 | 解除遮罩 + toast |
| 1030 | 时段限制（未成年 20:00-8:00 禁玩） | 全屏遮罩不可关 |
| 1050 | 当日时长耗尽 | 全屏遮罩不可关 |
| 1100 | 年龄限制（优先级最高） | 全屏遮罩不可关 |
| 9002 | 实名窗被玩家关闭 | 遮罩 +「重新认证」按钮（re-startup） |
| 1200 | ClientID 错或网络异常 | toast 提示，不拦截 |
| 1000/1001 | 退出/切换账号 | 遮罩提示 |

## 三、启用步骤（需要你的 TapTap 账号操作，机器代办不了）

1. **开通服务**： TapTap 开发者中心 → 游戏服务 → 开发与构建 → **合规认证** → 选「**暂无版号**」方案开通
2. **创建应用**： 开发者中心创建应用，拿到 **Client ID** 与 **Client Token**
3. **填配置**： 编辑 `game/js/anti-addiction.js` 顶部：
   ```js
   var CONFIG = { clientId: '你的ClientID', clientToken: '你的ClientToken' };
   ```
4. **重新打包**：
   ```bash
   cd game/mobile && python sync_www.py && cd android && ./gradlew assembleDebug
   ```
5. 实机验证：首次启动应弹出 TapTap 实名认证（手机装有 TapTap 可无缝授权）

## 四、顺带修复（v0.1 → v0.2）

- **v0.1 APK 缺陷**：staged www 缺 `js/vendor/peerjs.min.js`（好友房码在 APP 内必挂），
  已修并固化进 `mobile/sync_www.py`（同步后自动 `cap copy`，杜绝再漏）。
- privacy.html 增补防沉迷条款（TapTap 代实名、本游戏不收集身份信息）。
- 构建链固化：`sync_www.py`（webp-only 规则 564 文件）→ `cap copy` → `gradlew assembleDebug`。
- 产物：`game/yozora-poker-v0.2-debug.apk`（53.9MB → 实测 70.5MB 解包内容，含 TapSDK ~10MB）。

## 五、遗留提醒

- TapTap 后台「防沉迷策略配置」里可调未成年人可玩时段/时长展示文案——提审前过一眼默认值。
- 无版号方案下 `getAgeRange()` 可能恒返 -1（官方明示），本游戏未使用年龄段逻辑，无影响。
