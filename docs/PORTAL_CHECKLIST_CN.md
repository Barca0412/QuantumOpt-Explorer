# GOAI 复赛补交检查单

此清单用于组委会授权的补交窗口。公开赛程本身不能证明补交权限或具体截止时刻。

## 进入后台后先确认

- 补交窗口的北京时间截止时刻。
- 当前作品是否允许覆盖，以及覆盖后能否再次修改。
- 必填栏：仓库 URL、代码/环境包、探索日志、基线说明、技术报告、问题定义文档。
- 每个上传栏允许的格式、单文件大小和总大小。
- 是否需要把仓库设为公开，或向评委账号授权。
- 页面上的“保存”“提交”“最终确认”是否为不同状态。

## 推荐填写内容

- 项目名称：`QuantumOpt-Explorer`
- 赛道：`AI for Research - Open Exploration`
- 公开仓库：`https://github.com/Barca0412/QuantumOpt-Explorer`
- 固定版本：以 `RELEASE_MANIFEST.txt` 中的 tag 和 commit 为准。
- 主报告：`QuantumOpt-Explorer_Semifinal_Report.pdf`
- 环境与代码：优先上传完整 semifinal ZIP。
- 若代码栏限制过小：上传 portal-light ZIP，并在作品说明中明确完整环境、日志与 raw evidence 位于公开仓库固定 tag。

## 最终点击前

- 页面显示的参赛人、团队、赛道和项目名称均正确。
- 所有链接在未登录窗口可访问。
- 页面中的 commit SHA 与本地 `RELEASE_MANIFEST.txt` 一致。
- 上传文件 SHA256 与 `dist/SHA256SUMS.txt` 一致。
- PDF 可打开，页数完整，没有裁切、黑块或乱码。
- 未把 smoke 结果误填成 full result。
- 结论保留模拟、固定拓扑、无硬件验证和无新量子门主张。
- 点击最终提交后保存状态截图或回执；不要仅以文件上传进度条作为提交成功证据。
