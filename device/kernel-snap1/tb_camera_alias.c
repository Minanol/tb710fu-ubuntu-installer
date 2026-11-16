// SPDX-License-Identifier: GPL-2.0-only
/* Supply aliases for a manually bound TB710FU rear sensor test device. */
#include <linux/device.h>
#include <linux/i2c.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/regulator/consumer.h>

static char *client_name;
module_param(client_name, charp, 0400);
static struct device *client;
static const char * const supplies[] = { "dovdd", "avdd", "dvdd" };
static const char * const providers[] = {
	"vreg_l4b_1p8", "vreg_l16b_2p8", "vreg_l11b_1p2"
};

static int __init tb_alias_init(void)
{
	int i, ret;

	if (!client_name)
		return -EINVAL;
	client = bus_find_device_by_name(&i2c_bus_type, NULL, client_name);
	if (!client)
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(supplies); i++) {
		ret = regulator_register_supply_alias(client, supplies[i], client, providers[i]);
		if (ret)
			goto err;
	}
	pr_info("tb-camera-alias: supplies registered for %s\n", client_name);
	return 0;
err:
	while (i--)
		regulator_unregister_supply_alias(client, supplies[i]);
	put_device(client);
	return ret;
}

static void __exit tb_alias_exit(void)
{
	int i;
	for (i = 0; i < ARRAY_SIZE(supplies); i++)
		regulator_unregister_supply_alias(client, supplies[i]);
	put_device(client);
}
module_init(tb_alias_init);
module_exit(tb_alias_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("TB710FU rear camera temporary regulator aliases");
