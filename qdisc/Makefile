KDIR ?= /lib/modules/`uname -r`/build

obj-m += sch_react.o

all:
	make -C $(KDIR) M=$(CURDIR) modules

install:
	make -C $(KDIR) M=$(CURDIR) modules_install

clean:
	make -C $(KDIR) M=$(CURDIR) clean

tags:
	make -C $(KDIR) O=$(CURDIR) tags

.PHONY: all install clean tags
