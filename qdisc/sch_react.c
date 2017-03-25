#include <linux/module.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/kernel.h>
#include <linux/errno.h>
#include <linux/skbuff.h>
#include <net/pkt_sched.h>

struct sk_buff *skb_ctrl = NULL;

static int react_enqueue(struct sk_buff *skb, struct Qdisc *sch)
{
	if (skb_ctrl)
		qdisc_drop(skb_ctrl, sch);

	skb_ctrl = skb;
	sch->q.qlen = 1;

	return NET_XMIT_SUCCESS;
}

static struct sk_buff *react_dequeue(struct Qdisc *sch)
{
	struct sk_buff *tmp;

	tmp = skb_ctrl;
	skb_ctrl = NULL;
	sch->q.qlen = 0;

	return tmp;
}

struct sk_buff *react_peek(struct Qdisc *sch)
{
	return skb_ctrl;
}

struct Qdisc_ops react_qdisc_ops __read_mostly = {
	.id		=	"react",
	.priv_size	=	0,
	.enqueue	=	react_enqueue,
	.dequeue	=	react_dequeue,
	.peek		=	react_peek,
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
