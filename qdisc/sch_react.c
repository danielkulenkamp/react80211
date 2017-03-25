#include <linux/module.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/kernel.h>
#include <linux/errno.h>
#include <linux/skbuff.h>
#include <net/pkt_sched.h>

struct react_data {
	struct sk_buff *ctrl;
	struct Qdisc *q;
};

static int react_enqueue(struct sk_buff *skb, struct Qdisc *sch)
{
	struct react_data *dat = qdisc_priv(sch);
	int ret;

	/* Marked packets are control packets */
	if (skb->mark) {
		if (dat->ctrl)
			qdisc_drop(dat->ctrl, sch);

		dat->ctrl = skb;
		sch->q.qlen++;
		return NET_XMIT_SUCCESS;
	}

	ret = qdisc_enqueue(skb, dat->q);
	if (ret == NET_XMIT_SUCCESS)
		sch->q.qlen++;
	return ret;
}

static struct sk_buff *react_dequeue(struct Qdisc *sch)
{
	struct react_data *dat = qdisc_priv(sch);
	struct sk_buff *skb;

	/* Always send a control packet if there is one */
	if (dat->ctrl) {
		skb = dat->ctrl;
		dat->ctrl = NULL;
	} else
		skb = dat->q->dequeue(dat->q);

	if (skb)
		sch->q.qlen--;
	return skb;
}

static int react_init(struct Qdisc *sch, struct nlattr *opt)
{
	struct react_data *dat = qdisc_priv(sch);

	dat->ctrl = NULL;

	/* All packets other than control packets go in this FIFO */
	dat->q = qdisc_create_dflt(sch->dev_queue, &pfifo_qdisc_ops, 0);
	if (!dat->q)
		return -ENOMEM;

	return 0;
}

struct Qdisc_ops react_qdisc_ops __read_mostly = {
	.id		=	"react",
	.priv_size	=	sizeof(struct react_data),
	.enqueue	=	react_enqueue,
	.dequeue	=	react_dequeue,
	.peek		=	qdisc_peek_dequeued,
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
