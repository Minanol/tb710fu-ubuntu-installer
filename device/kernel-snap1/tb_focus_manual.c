// SPDX-License-Identifier: GPL-2.0-only
/* Temporary GT9772B manual-focus experiment. No automatic loading. */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/init.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>
#include <linux/swab.h>

static int bus = -1;
module_param(bus, int, 0400);
static int position = -1, initial_position = -1;
static struct i2c_adapter *adapter;
static struct regulator *vio, *vaf;
static DEFINE_MUTEX(focus_lock);

static int focus_write(u16 pos)
{
	union i2c_smbus_data d = { .word = swab16(pos) };
	return i2c_smbus_xfer(adapter, 0x0c, 0, I2C_SMBUS_WRITE,
			      0x03, I2C_SMBUS_WORD_DATA, &d);
}

static int focus_move(int target)
{
	int next, ret;
	while (position != target) {
		next = position + clamp(target - position, -40, 40);
		ret = focus_write(next);
		if (ret < 0)
			return ret;
		position = next;
		usleep_range(5000, 6000);
	}
	return 0;
}

static int focus_set(const char *value, const struct kernel_param *kp)
{
	int target, ret;
	ret = kstrtoint(value, 0, &target);
	if (ret || target < 0 || target > 1023)
		return -EINVAL;
	mutex_lock(&focus_lock);
	ret = adapter && position >= 0 ? focus_move(target) : -ENODEV;
	mutex_unlock(&focus_lock);
	return ret;
}

static const struct kernel_param_ops focus_ops = {
	.set = focus_set,
	.get = param_get_int,
};
module_param_cb(position, &focus_ops, &position, 0644);

static int __init focus_init(void)
{
	union i2c_smbus_data data;
	int ret;
	if (bus < 0)
		return -EINVAL;
	adapter = i2c_get_adapter(bus);
	if (!adapter)
		return -ENODEV;
	if (!adapter->dev.of_node ||
	    !of_node_name_eq(adapter->dev.of_node, "i2c-bus") ||
	    !of_node_name_eq(adapter->dev.of_node->parent, "cci")) {
		ret = -ENODEV;
		goto put_adapter;
	}
	vio = regulator_get(&adapter->dev, "vreg_l4b_1p8");
	if (IS_ERR(vio)) { ret = PTR_ERR(vio); goto put_adapter; }
	vaf = regulator_get(&adapter->dev, "vreg_l9b_2p9");
	if (IS_ERR(vaf)) { ret = PTR_ERR(vaf); goto put_vio; }
	if (regulator_get_voltage(vio) != 1800000 || regulator_get_voltage(vaf) != 2800000) {
		ret = -EINVAL; goto put_vaf;
	}
	ret = regulator_enable(vio);
	if (ret) goto put_vaf;
	ret = regulator_enable(vaf);
	if (ret) goto disable_vio;
	usleep_range(10000, 11000);
	ret = i2c_smbus_xfer(adapter, 0x0c, 0, I2C_SMBUS_READ, 0x00,
			     I2C_SMBUS_BYTE_DATA, &data);
	if (ret < 0 || data.byte != 0xf2) { ret = -ENODEV; goto disable_vaf; }
	ret = i2c_smbus_xfer(adapter, 0x0c, 0, I2C_SMBUS_READ, 0x03,
			     I2C_SMBUS_WORD_DATA, &data);
	if (ret < 0) goto disable_vaf;
	position = swab16(data.word);
	if (position > 1023) { ret = -EINVAL; goto disable_vaf; }
	initial_position = position;
	data.byte = 0xab;
	ret = i2c_smbus_xfer(adapter, 0x0c, 0, I2C_SMBUS_WRITE, 0xed,
			     I2C_SMBUS_BYTE_DATA, &data);
	if (ret < 0) goto disable_vaf;
	pr_info("tb-focus-manual: initial position %d\n", position);
	return 0;
disable_vaf:
	regulator_disable(vaf);
disable_vio:
	regulator_disable(vio);
put_vaf:
	regulator_put(vaf);
put_vio:
	regulator_put(vio);
put_adapter:
	i2c_put_adapter(adapter);
	adapter = NULL;
	return ret;
}

static void __exit focus_exit(void)
{
	int ret;
	mutex_lock(&focus_lock);
	ret = focus_move(initial_position);
	if (ret)
		pr_err("tb-focus-manual: restoring initial position failed: %d\n", ret);
	regulator_disable(vaf);
	regulator_disable(vio);
	regulator_put(vaf);
	regulator_put(vio);
	i2c_put_adapter(adapter);
	adapter = NULL;
	mutex_unlock(&focus_lock);
}
module_init(focus_init);
module_exit(focus_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("TB710FU temporary manual camera focus experiment");
