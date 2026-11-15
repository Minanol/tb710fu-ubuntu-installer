# TB710FU Ubuntu 单系统安装器 0.1.0-preview

针对 Lenovo TB710FU 的 Ubuntu 单系统实验性安装器。设备端安装和 Ubuntu 启动已在 TB710FU 上测试；**本版本的 Windows 端到端安装尚未实机验证**。使用者应准备本机恢复方案。

安装会清除目标 userdata 或现有 arch 分区中的安卓和 Ubuntu 数据，不支持保留安卓或设置安卓分区大小。需要已解锁的 Bootloader、fastboot 驱动、Windows 本地磁盘至少 40 GiB 空闲空间以及可靠的 USB 数据连接。不要重锁 Bootloader。

从本仓库的 Releases 下载预览版启动包，解压后运行 `windows/install.cmd`。程序会请求管理员权限、要求输入 `ERASE`，并联网下载与校验系统镜像分片。安装完成后平板重启并进入 Ubuntu 首次设置，使用者自行创建账户。安装器的工作目录含设备专属数据，请勿公开。

系统包含 200% 默认显示缩放、自定义电源键菜单、皮套背光、中文输入和后摄适配。电源和皮套修复按活动图形会话选择用户，不预设账户名。启动菜单上的 Linux 选项显示为 Ubuntu；它基于原 Ubuntu 启动镜像，内核和设备树未更改。

`device/` 包含设备端安装逻辑，`windows/` 是 Windows 安装入口，`tools/` 包含 NBD 服务器与启动镜像相关工具，`desktop/` 包含桌面适配源码。此仓库不提供完整的镜像重建环境；部分构建工具需要另行取得相应上游源码、工具链和输入。

Kimpanel 修改文件继承上游 GPL-2.0-or-later，许可证见 `desktop/kimpanel/COPYING`。NBD 服务器与部分启动工具源自 [TB710FU Arch Linux port](https://github.com/deinthoedoka/TB710FU-Archlinux)，遵循其附带的许可。发行文件包含硬件固件，固件来源及再分发许可需要使用者核实。设备备份、个人数据、凭据、设备唯一标识和已停止的前摄实验不属于本仓库。
