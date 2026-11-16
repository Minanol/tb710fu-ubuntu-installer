// SPDX-License-Identifier: GPL-2.0-only
/* Temporary, explicitly loaded device-tree overlay for TB710FU diagnostics. */
#include <linux/firmware.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/of.h>

static char *overlay_name = "tb710fu-overlay-check.dtbo";
module_param(overlay_name, charp, 0400);
MODULE_PARM_DESC(overlay_name, "Firmware filename containing a test overlay");
static int overlay_id = -1;

static int __init tb_overlay_init(void)
{
	const struct firmware *fw;
	int ret;

	ret = request_firmware_direct(&fw, overlay_name, NULL);
	if (ret) {
		pr_err("tb-camera-overlay: firmware request failed: %d\n", ret);
		return ret;
	}
	ret = of_overlay_fdt_apply(fw->data, fw->size, &overlay_id, NULL);
	release_firmware(fw);
	if (ret) {
		if (overlay_id >= 0)
			of_overlay_remove(&overlay_id);
		pr_err("tb-camera-overlay: apply failed: %d\n", ret);
		return ret;
	}
	pr_info("tb-camera-overlay: applied id %d\n", overlay_id);
	return 0;
}

static void __exit tb_overlay_exit(void)
{
	int ret = of_overlay_remove(&overlay_id);
	if (ret)
		pr_err("tb-camera-overlay: remove failed: %d; reboot required\n", ret);
	else
		pr_info("tb-camera-overlay: removed\n");
}

module_init(tb_overlay_init);
module_exit(tb_overlay_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("TB710FU temporary OF overlay loader for diagnostics");
