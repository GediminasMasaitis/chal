VERSION = 1.3.2
CC      = gcc
CFLAGS  = -O2 -Wall -Wextra -pedantic -std=gnu99 -DFULL -DVERSION=\"$(VERSION)\"
LDFLAGS = -lm

# Cross-platform
ifeq ($(OS),Windows_NT)
    TARGET = bin/chal.exe
    RM     = powershell -Command "Remove-Item -Path $(TARGET) -ErrorAction SilentlyContinue"
    MKDIR  = powershell -Command "if(-not(Test-Path bin)){New-Item -ItemType Directory -Path bin}"
else
    TARGET = bin/chal
    RM     = rm -f
    MKDIR  = mkdir -p bin
endif

.PHONY: all debug clean perft minify loader

all: $(TARGET)

debug: CFLAGS = -g -O0 -Wall -Wextra -pedantic -std=gnu99 -DVERSION=\"$(VERSION)\"
debug: $(TARGET)

$(TARGET): src/chal.c Makefile
	$(MKDIR)
	$(CC) $(CFLAGS) src/chal.c -o $(TARGET) $(LDFLAGS)

perft: $(TARGET)
	$(TARGET) perft 6

minify:
	python minify.py src/chal.c src/chal_mini.c
	xz -f -k src/chal_mini.c
	ls -l src/chal_mini.c.xz

minify-full:
	python minify.py -DFULL src/chal.c src/chal_mini.c
	xz -f -k src/chal_mini.c
	ls -l src/chal_mini.c.xz

loader: minify
	printf '#!/bin/sh\nT=`mktemp`\ntail -n +5 "$$0"|xz -d|cc -o $$T -O3 -xc - -lm\n(sleep 3;rm $$T)&exec $$T\n' > bin/chal.sh
	cat src/chal_mini.c.xz >> bin/chal.sh
	chmod +x bin/chal.sh
	ls -l bin/chal.sh

clean:
	$(RM) $(TARGET)
