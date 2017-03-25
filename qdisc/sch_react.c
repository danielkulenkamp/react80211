#include <linux/module.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/kernel.h>
#include <linux/errno.h>
#include <linux/skbuff.h>
#include <net/pkt_sched.h>

struct react_data {
	struct sk_buff *ctrl;
};

static int react_enqueue(struct sk_buff *skb, struct Qdisc *sch)
{
	struct react_data *dat = qdisc_priv(sch);

	if (dat->ctrl)
		qdisc_drop(dat->ctrl, sch);

	dat->ctrl = skb;
	sch->q.qlen = 1;

	return NET_XMIT_SUCCESS;
}

static struct sk_buff *react_dequeue(struct Qdisc *sch)
{
	struct sk_buff *tmp;
	struct react_data *dat = qdisc_priv(sch);

	tmp = dat->ctrl;
	dat->ctrl = NULL;
	sch->q.qlen = 0;

	return tmp;
}

struct sk_buff *react_peek(struct Qdisc *sch)
{
	struct react_data *dat = qdisc_priv(sch);
	return dat->ctrl;
}

static int react_init(struct Qdisc *sch, struct nlattr *opt)
{
	struct react_data *dat = qdisc_priv(sch);

	dat->ctrl = NULL;

	return 0;
}

struct Qdisc_ops react_qdisc_ops __read_mostly = {
	.id		=	"react",
	.priv_size	=	sizeof(struct react_data),
	.enqueue	=	react_enqueue,
	.dequeue	=	react_dequeue,
	.peek		=	react_peek,
	.init		=	react_init,
	.owner		=	THIS_MODULE,
};

static int __init react_module_init(void)
{
	printk("sch_react: Compiled on " __DATE__ " at %s\n", __TIME__);
	return register_qdisc(&react_qdisc_ops);
}

static void __exit react_module_exit(void)
{
	unregister_qdisc(&react_qdisc_ops);
}

module_init(react_module_init)
module_exit(react_module_exit)
MODULE_LICENSE("GPL");
