# snap1 内核及麦克风适配源码

这些文件是发布镜像中使用的 snap1 构建脚本、配置、AppArmor 兼容补丁、已使用的后摄 OV13B10/CAMSS 源码和麦克风路由脚本。构建依赖上游 Linux 7.2.6、Freedom 和 TB710FU 补丁、工具链、原启动基线及 initramfs；此目录本身不是完整构建环境。baseline.config 的 initramfs 路径已清空，避免携带本地路径。

麦克风设备树从已验证原始 Ubuntu DT 派生：构建 WCD capture link，TX SoundWire 使用 Pin1，启动时设置 AMIC1/AMIC3 路由。脚本保留原离线实验文件名，仅作源码与操作说明；不要在未检查设备当前固件和分区表的情况下刷写。前摄实验不包含在这里。

构建输入还包括 [Linux 7.2.6](https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.2.6.tar.xz)（SHA256 `039aef84f2b0994aeda3f4fcfc3d02ec9d7a9bbb9020ea264c43f446c860f606`）、[Freedom](https://github.com/mydanyi/armadaos-freedom/tree/ba692d8c06fc1d5d7cafe91325448b19765a7b08)、[TB710FU HyperOS SteamOS](https://github.com/lich-wang/tb710fu-hyperos-steamos/tree/5e99ee13df849f592a4594910473f1bbdbd79ee3) 和 [TB710FU Arch Linux](https://github.com/deinthoedoka/TB710FU-Archlinux/tree/110fbccb59ed3ea3bc323fc05601ad6fd442f02d) 的对应修补。Linux 派生文件保留原 SPDX 和版权声明，GPL-2.0 许可见本目录 COPYING。启动镜像的 initramfs 和固件是独立输入，不包含个人设备备份。
