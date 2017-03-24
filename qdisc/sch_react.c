#include <linux/module.h>
#include <linux/slab.h>
#include <linux/types.h>
#include <linux/kernel.h>
#include <linux/errno.h>
#include <linux/skbuff.h>
#include <net/pkt_sched.h>

static int react_enqueue(struct sk_buff *skb, struct Qdisc *sch)
{
	/* Got more up-to-date data, empty queue */
	while (__skb_dequeue(&sch->q));

	return qdisc_enqueue_tail(skb, sch);
}

static int react_init(struct Qdisc *sch, struct nlattr *opt)
{
	/* Only keep the most up-to-date control packet */
	sch->limit = 1;

	//sch->flags &= ~TCQ_F_CAN_BYPASS;

	return 0;
}

struct Qdisc_ops react_qdisc_ops __read_mostly = {
	.id		=	"react",
	.priv_size	=	0,
	.enqueue	=	react_enqueue,
	.dequeue	=	qdisc_dequeue_head,
	.peek		=	qdisc_peek_head,
	.drop		=	qdisc_queue_drop,
	.init		=	react_init,
	.reset		=	qdisc_reset_queue,
	.change		=	react_init,
	//.dump		=	fifo_dump,
	.owner		=	THIS_MODULE,
};

static int __init react_module_init(void)
{
	return register_qdisc(&react_qdisc_ops);
}

static void __exit react_module_exit(void)
{
	unregister_qdisc(&react_qdisc_ops);
}

module_init(react_module_init)
module_exit(react_module_exit)

MODULE_LICENSE("GPL");
