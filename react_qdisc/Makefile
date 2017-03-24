CC = gcc-4.9
KBUILD_DIR = /home/matt/linux-3.8

obj-m += sch_react.o

all:
	make -C $(KBUILD_DIR) M=$(PWD) modules

clean:
	make -C $(KBUILD_DIR) M=$(PWD) clean

tags:
	make -C $(KBUILD_DIR) O=$(PWD) tags

