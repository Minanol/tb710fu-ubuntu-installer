// SPDX-License-Identifier: GPL-2.0-only
#include <linux/device.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/regulator/consumer.h>

static struct device *camss;
static const char * const supplies[] = {
	"vdd-csiphy01-0p9", "vdd-csiphy01-1p2",
	"vdd-csiphy24-0p9", "vdd-csiphy24-1p2",
	"vdd-csiphy35-0p9", "vdd-csiphy35-1p2"
};
static const char * const providers[] = {
	"vreg_l2i_0p88", "vreg_l3i_1p2",
	"vreg_l2i_0p88", "vreg_l3i_1p2",
	"vreg_l2i_0p88", "vreg_l3i_1p2"
};

static int __init camss_alias_init(void)
{
	int i, ret;
	camss = bus_find_device_by_name(&platform_bus_type, NULL, "acb6000.isp");
	if (!camss)
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(supplies); i++) {
		ret = regulator_register_supply_alias(camss, supplies[i], camss, providers[i]);
		if (ret)
			goto err;
	}
	pr_info("tb-camss-alias: supplies registered\n");
	return 0;
err:
	while (i--)
		regulator_unregister_supply_alias(camss, supplies[i]);
	put_device(camss);
	return ret;
}

static void __exit camss_alias_exit(void)
{
	int i;
	for (i = 0; i < ARRAY_SIZE(supplies); i++)
		regulator_unregister_supply_alias(camss, supplies[i]);
	put_device(camss);
}
module_init(camss_alias_init);
module_exit(camss_alias_exit);
MODULE_LICENSE("GPL");
