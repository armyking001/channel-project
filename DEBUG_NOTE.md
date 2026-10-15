# 渠道项目管理系统 - 文件显示问题诊断笔记

## 问题描述
项目列表中点击「编辑项目（仅上传文件）」弹窗中，文件管理区域始终显示「暂无文件」。
后端用相同 payload 直接调用可以返回文件列表（如 _test_demo.txt, capture_file_*.pcap, 采购文件.docx, 采购文件.pdf）。

## 环境
- 前端: Vite + React + Axios
- 后端: FastAPI + requests 库调用 Synology WebDAV
- WebDAV 服务器: Synology NAS (https://172.16.10.252:5006)
- 关键目录: /渠道资料/刘建辉+洪山区公安分局...智慧警营升级改造信息化设备采购项目+2026-08-04/招标资料

## 已尝试的修复（按时间顺序）
1. 浏览器缓存 → 给 /admin/* 加 no-cache 头
2. 前端 fetchFiles 函数加兼容性代码：在 target_dir 字符串中「采」「购」之间插入空格
3. 后端 list_files_webdav：第一次 PROPFIND 返回 4xx 时，自动尝试多种 URL 变体
4. 后端 _request：自动把 URL 中「汉字之间的裸空格」转 %20 编码
5. 后端 list_files_webdav：用 project_name_hint 找出所有「插入 1 个空格」的变体（30+ 种）
6. 前端再次升级：通用启发式 - 在最长汉字 run 倒数第 1 个位置前插空格

## 当前已知事实（最重要）

**事实 1（已确认）**：
后端 _diag_repro.py / _diag_frontend.py 调用 list-files 接口：
- tender 路径：返回 4 个文件 ✅
- bid 路径：返回 0 个文件（目录本身空，正常）

**事实 2（用户最新截图）**：
浏览器打开洪山项目编辑弹窗，左下角调试条显示：
- `[fetch-result] bid = 0 files. folder_tail="...采 购项目+2026-08-04/投标文档" names=""`
- `[after-setTender] 1s later, files should be 0`
- `[fetch] bid hasSpace=true hasNoSpace=false len=68 tail="...采 购项目+2026-08-04/投标文档"`

**重要观察**：
- `bid` 调试条已显示：target_dir 已包含空格（hasSpace=true），后端返回 0 个文件 - 符合预期
- `tender` 调试条**没显示**（底部被截掉 / 已被覆盖）
- `after-setTender` 显示 `files should be 0` - 即前端 fetchFiles 给 tender 发请求时**也**拿到了 0 个文件

**矛盾点**：
- 后端 _diag_repro.py 用前端同样的 payload 调用 → 4 个文件
- 浏览器前端 fetchFiles 用同样的 payload 调用 → 0 个文件
- 唯一区别：浏览器调用经过额外的 React fetchFiles 函数 + 我的兼容性代码（替换 target_dir）

**事实 3（前端兼容代码细节）**：
```js
// ProjectForm.jsx fetchFiles 函数内
if (existingDir && !existingDir.includes(' ')) {
  const hanRunRe = /[\u4e00-\u9fff]{4,}/g
  const runs = existingDir.match(hanRunRe) || []
  if (runs.length > 0) {
    const longest = runs.reduce((a, b) => a.length >= b.length ? a : b)
    const newRun = longest.slice(0, -1) + ' ' + longest.slice(-1)
    payload.target_dir = existingDir.replace(longest, newRun)
  }
}
```

bid 调试条说 `hasSpace=true`，说明这条兼容代码对 bid 起作用了（在 target_dir 中插入了空格）。
那 tender 应该也一样插入了空格（因为 target_dir 都是同样的"无空格版"）。

## 可能原因（需要新思路）

### 假设 A：多次 useEffect 触发 fetchFiles 互相覆盖
- ProjectForm 有两个 useEffect 触发 fetchFiles
- 第一个 useEffect 用 setTimeout(300ms) 后串行调用 tender + bid
- 第二个 useEffect（兜底）用 [project?.id] 依赖也会触发
- **关键**：第二个 useEffect 的 fetchFiles 调用没有 setTimeout 包裹，**会立即**调用
- 那么调用顺序可能是：tender(即时) → bid(即时) → tender(300ms后) → bid(300ms后)
- 如果即时的 bid 调用**晚于**300ms后的 bid 调用，结果就会错位
- 但这只解释错位，不解释为什么 tender 也是 0

### 假设 B：第二次 fetchFiles 的 payload.target_dir 不是用户输入的项目名对应的路径
- `existingDir = folderType === 'tender' ? project?.tender_folder : project?.bid_folder`
- 如果 project.tender_folder 在前端状态中实际是空串或 undefined，那么 payload.target_dir 是 undefined
- 兼容性代码 `if (existingDir && !existingDir.includes(' '))` 不进入
- 后端收到 payload 没有 target_dir 字段 → 后端用 project_name + creator_username 重新拼路径
- 拼出的路径**不带空格**（因为数据库的字段是"无空格版" project_name）
- 后端调用 WebDAV 拿到 0 个文件

### 假设 C：后端 list_files_webdav 容错超时
- _space_variants_for_project 对 project_name "洪山区公安分局...信息化设备采购项目" 生成 31 种变体
- 每次 PROPFIND 1-2 秒 → 总耗时 30-60 秒
- 请求被前端 axios 超时（默认无超时）或者中间断开
- 31 种变体中没有"信息?设备采 购项目"（last_1 char 是"目"，倒数第 2 是"项"）

等等！**C 假设有 bug**：
我的前端兼容代码：`longest.slice(0, -1) + ' ' + longest.slice(-1)`
- longest = "洪山区公安分局...信息化设备采购项目"
- longest.slice(-1) = "目"
- longest.slice(0, -1) = "洪山区公安分局...信息化设备采购项"
- newRun = "洪山区公安分局...信息化设备采购项 目"
- 即插入位置在 "项" 和 "目" 之间 - **不是 "采" 和 "购" 之间！**

但 bid 调试条 tail 显示 `采 购项目`（最后 5 个字符），说明 bid **真的**正确插入到 "采" 和 "购" 之间。
那是因为 bid 的 `existingDir` 不是同一个 longest。**或者** longest 匹配的不是 project_name 全字符串，是 URL 里其他段。

## 需要检查的关键代码路径
1. ProjectForm.jsx 中的 fetchFiles 函数
2. listStorageFiles (api 调用)
3. 后端 app/routers/file_storage.py 中 list-files endpoint
4. 后端 app/services/webdav_client.py 中 list_files_webdav
5. ProjectForm 中两个 useEffect 的依赖数组

## 请诊断的方向
- 浏览器 DevTools Network 标签：过滤 list-files，找到 tender 那个请求，看 Request Payload 中 target_dir 实际是含空格还是不含空格
- 如果是含空格 → 后端容错是不是有问题
- 如果是不含空格 → 前端兼容代码没生效，project.tender_folder 是不是空
- 还可以看 Response 中 files 数组长度
- Console 标签里 `[setTenderFiles]` 那一行 console.log 输出

## 关键文件路径
- frontend/src/components/ProjectForm.jsx (line 92-150 是 fetchFiles)
- backend/app/routers/file_storage.py (list-files endpoint)
- backend/app/services/webdav_client.py (list_files_webdav)
- backend/app_debug.log (后端运行日志)