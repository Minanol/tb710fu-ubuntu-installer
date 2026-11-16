# TB710FU Ubuntu 单系统安装器 0.2.0-preview

针对 Lenovo TB710FU 的 Ubuntu 单系统实验性安装器。本版本的 Windows 端到端安装及现有 Ubuntu 保留数据覆盖尚未实机验证；使用者需要备份并准备恢复方案。

有两种安装模式：安卓首次安装或清空重装会删除目标 userdata/arch 分区的全部内容；现有 Ubuntu 覆盖模式支持受限制的 arch ext4 布局，尝试保留账户、/home 下的个人文件和用户设置，系统文件及部分系统设置可能被替换。它不支持保留安卓、调整安卓分区大小、独立 /home 或不兼容账户。保留模式在检查文件系统之前先写入临时 boot_a，如果检查失败可能需要恢复启动镜像；请先备份。

需要已解锁的 Bootloader、fastboot 驱动、Windows 本地磁盘至少 40 GiB 空闲及可靠的数据线。不要重锁 Bootloader。从 Releases 下载启动包，在 Windows 解压并运行 `windows/install.cmd`。按提示选择模式并输入 ERASE 或 KEEP。镜像分片联网下载并校验；安装完成后重启 Ubuntu。不要公开安装工作目录。

系统包含 200% 默认缩放、自定义电源键、皮套背光、输入法和后摄适配。账户名通过活动会话识别。启动镜像基于原有 Ubuntu 启动基线并包括后续的 Snap 和麦克风修复；本版本修复尚待覆盖安装实机确认。

`device/` 是设备端安装逻辑，`windows/` 是 Windows 入口，`tools/` 包含 NBD 服务器与构建工具，`desktop/` 包含桌面适配源码。本仓库不提供完整镜像重建环境；部分组件需要上游源码、工具链和输入。

Kimpanel 修改继承 GPL-2.0-or-later，许可见 `desktop/kimpanel/COPYING`。NBD 服务器和部分启动工具源自 [TB710FU Arch Linux port](https://github.com/deinthoedoka/TB710FU-Archlinux)，遵循附带许可。发行文件包含硬件固件，其再分发许可需要核实。设备备份、个人数据、凭据、设备唯一标识和已停止的前摄实验不属于公开内容。

公开镜像不包含 QQ、WorkBuddy、FlClash 或 Google Chrome；提供 GNOME Web 浏览器，其他应用由使用者自行获取。
