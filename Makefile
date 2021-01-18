
MAKEFLAGS += --warn-undefined-variables

SHELL := bash
.DEFAULT_GOAL := all

clean_paths :=

# See config/config.vars.in (sets bup_python_config, among other things)
include config/config.vars

pf := set -o pipefail

define isok
  && echo " ok" || echo " no"
endef

# If ok, strip trailing " ok" and return the output, otherwise, error
define shout
$(if $(subst ok,,$(lastword $(1))),$(error $(2)),$(shell x="$(1)"; echo $${x%???}))
endef

sampledata_rev := $(shell dev/configure-sampledata --revision $(isok))
sampledata_rev := \
  $(call shout,$(sampledata_rev),Could not parse sampledata revision)

current_sampledata := test/sampledata/var/rev/v$(sampledata_rev)

os := $(shell ($(pf); uname | sed 's/[-_].*//') $(isok))
os := $(call shout,$(os),Unable to determine OS)

CFLAGS := -O2 -Wall -Werror -Wformat=2 $(CFLAGS)
CFLAGS := -Wno-unknown-pragmas -Wsign-compare $(CFLAGS)
CFLAGS := -D_FILE_OFFSET_BITS=64 $(CFLAGS)
SOEXT:=.so

ifeq ($(os),CYGWIN)
  SOEXT:=.dll
endif

ifdef TMPDIR
  test_tmp := $(TMPDIR)
else
  test_tmp := $(CURDIR)/test/tmp
endif

initial_setup := $(shell dev/update-checkout-info lib/bup/checkout_info.py $(isok))
initial_setup := $(call shout,$(initial_setup),update-checkout-info failed))
clean_paths += lib/bup/checkout_info.py

config/config.vars: \
  configure config/configure config/configure.inc \
  $(wildcard config/*.in)
	MAKE="$(MAKE)" ./configure

# On some platforms, Python.h and readline.h fight over the
# _XOPEN_SOURCE version, i.e. -Werror crashes on a mismatch, so for
# now, we're just going to let Python's version win.

ifneq ($(strip $(bup_readline_cflags)),)
  readline_cflags += $(bup_readline_cflags)
  readline_xopen := $(filter -D_XOPEN_SOURCE=%,$(readline_cflags))
  readline_xopen := $(subst -D_XOPEN_SOURCE=,,$(readline_xopen))
  readline_cflags := $(filter-out -D_XOPEN_SOURCE=%,$(readline_cflags))
  readline_cflags += $(addprefix -DBUP_RL_EXPECTED_XOPEN_SOURCE=,$(readline_xopen))
  CFLAGS += $(readline_cflags)
endif

LDFLAGS += $(bup_readline_ldflags)

ifeq ($(bup_have_libacl),1)
  CFLAGS += $(bup_libacl_cflags)
  LDFLAGS += $(bup_libacl_ldflags)
endif

bup_ext_cmds := lib/cmd/bup-import-rdiff-backup lib/cmd/bup-import-rsnapshot

bup_deps := lib/bup/_helpers$(SOEXT) lib/cmd/bup

all: dev/bup-exec dev/bup-python dev/python $(bup_deps) Documentation/all \
  $(current_sampledata)

$(current_sampledata):
	dev/configure-sampledata --setup

PANDOC ?= $(shell type -p pandoc)

ifeq (,$(PANDOC))
  $(shell echo "Warning: pandoc not found; skipping manpage generation" 1>&2)
  man_md :=
else
  man_md := $(wildcard Documentation/*.md)
endif

man_roff := $(patsubst %.md,%.1,$(man_md))
man_html := $(patsubst %.md,%.html,$(man_md))

INSTALL=install
PREFIX=/usr/local
MANDIR=$(PREFIX)/share/man
DOCDIR=$(PREFIX)/share/doc/bup
BINDIR=$(PREFIX)/bin
LIBDIR=$(PREFIX)/lib/bup

dest_mandir := $(DESTDIR)$(MANDIR)
dest_docdir := $(DESTDIR)$(DOCDIR)
dest_bindir := $(DESTDIR)$(BINDIR)
dest_libdir := $(DESTDIR)$(LIBDIR)

install: all
	$(INSTALL) -d $(dest_bindir) $(dest_libdir)/bup/cmd $(dest_libdir)/cmd \
	  $(dest_libdir)/web/static
	test -z "$(man_roff)" || install -d $(dest_mandir)/man1
	test -z "$(man_roff)" || $(INSTALL) -m 0644 $(man_roff) $(dest_mandir)/man1
	test -z "$(man_html)" || install -d $(dest_docdir)
	test -z "$(man_html)" || $(INSTALL) -m 0644 $(man_html) $(dest_docdir)
	$(INSTALL) -pm 0755 lib/cmd/bup "$(dest_libdir)/cmd/bup"
	$(INSTALL) -pm 0755 $(bup_ext_cmds) "$(dest_libdir)/cmd/"
	cd "$(dest_bindir)" && \
	  ln -sf "$$($(bup_python) -c 'import os; print(os.path.relpath("$(abspath $(dest_libdir))/cmd/bup"))')"
	set -e; \
	$(INSTALL) -pm 0644 lib/bup/*.py $(dest_libdir)/bup/
	$(INSTALL) -pm 0644 lib/bup/cmd/*.py $(dest_libdir)/bup/cmd/
	$(INSTALL) -pm 0755 \
		lib/bup/*$(SOEXT) \
		$(dest_libdir)/bup
	$(INSTALL) -pm 0644 \
		lib/web/static/* \
		$(dest_libdir)/web/static/
	$(INSTALL) -pm 0644 \
		lib/web/*.html \
		$(dest_libdir)/web/
	if test -e lib/bup/checkout_info.py; then \
	    $(INSTALL) -pm 0644 lib/bup/checkout_info.py \
	        $(dest_libdir)/bup/source_info.py; \
	else \
	    ! grep -qF '$$Format' lib/bup/source_info.py; \
	    $(INSTALL) -pm 0644 lib/bup/source_info.py $(dest_libdir)/bup/; \
	fi

config/config.h: config/config.vars
clean_paths += config/config.h.tmp

dev/python: dev/python.c config/config.h
	$(CC) $(bup_python_cflags_embed) $< $(bup_python_ldflags_embed) -o $@-proposed
	dev/validate-python $@-proposed
	mv $@-proposed $@
# Do not add to clean_paths - want it available until the very end

dev/bup-exec: lib/cmd/bup.c config/config.h
	$(CC) $(bup_python_cflags_embed) $< $(bup_python_ldflags_embed) -fPIC \
	  -D BUP_DEV_BUP_EXEC=1 -o $@
clean_paths += dev/bup-exec

dev/bup-python: lib/cmd/bup.c config/config.h
	$(CC) $(bup_python_cflags_embed) $< $(bup_python_ldflags_embed) -fPIC \
	  -D BUP_DEV_BUP_PYTHON=1 -o $@
clean_paths += dev/bup-python

lib/cmd/bup: lib/cmd/bup.c config/config.h
	$(CC) $(bup_python_cflags_embed) $< $(bup_python_ldflags_embed) -fPIC -o $@
clean_paths += lib/cmd/bup

helper_src := config/config.h lib/bup/bupsplit.h lib/bup/bupsplit.c
helper_src += lib/bup/_helpers.c

lib/bup/_helpers$(SOEXT): dev/python $(helper_src)
	$(CC) $(bup_python_cflags) $(CFLAGS) -shared -fPIC $(helper_src) \
	  $(bup_python_ldflags) $(LDFLAGS) -o $@
clean_paths += lib/bup/_helpers$(SOEXT)

test/tmp:
	mkdir test/tmp

# MAKEFLAGS must not be in an immediate := assignment
parallel_opt = $(lastword $(filter -j%,$(MAKEFLAGS)))
get_parallel_n = $(patsubst -j%,%,$(parallel_opt))
maybe_specific_n = $(if $(filter -j%,$(parallel_opt)),-n$(get_parallel_n))
xdist_opt = $(if $(filter -j,$(parallel_opt)),-nauto,$(maybe_specific_n))

test: all test/tmp dev/python
	if test yes = $$(dev/python -c "import xdist; print('yes')" 2>/dev/null); then \
	  (set -x; ./pytest $(xdist_opt);) \
	else \
	  (set-x; ./pytest;) \
	fi

stupid:
	PATH=/bin:/usr/bin $(MAKE) test

check: test

distcheck: all
	if test yes = $$(dev/python -c "import xdist; print('yes')" 2>/dev/null); then \
	  (set -x; ./pytest $(xdist_opt) -m release;) \
	else \
	  (set -x; ./pytest -m release;) \
	fi

long-test: export BUP_TEST_LEVEL=11
long-test: test

long-check: export BUP_TEST_LEVEL=11
long-check: check

.PHONY: check-both
check-both:
	$(MAKE) clean && PYTHON_CONFIG=python3-config $(MAKE) check
	$(MAKE) clean && PYTHON_CONFIG=python2.7-config $(MAKE) check

.PHONY: Documentation/all
Documentation/all: $(man_roff) $(man_html)

Documentation/substvars: $(bup_deps)
	echo "s,%BUP_VERSION%,$$(./bup version),g" > $@
	echo "s,%BUP_DATE%,$$(./bup version --date),g" >> $@

Documentation/%.1: Documentation/%.md Documentation/substvars
	$(pf); sed -f Documentation/substvars $< \
	  | $(PANDOC) -s -r markdown -w man -o $@

Documentation/%.html: Documentation/%.md Documentation/substvars
	$(pf); sed -f Documentation/substvars $< \
	  | $(PANDOC) -s -r markdown -w html -o $@

.PHONY: Documentation/clean
Documentation/clean:
	cd Documentation && rm -f *~ .*~ *.[0-9] *.html substvars

# Note: this adds commits containing the current manpages in roff and
# html format to the man and html branches respectively.  The version
# is determined by "git describe --always".
.PHONY: update-doc-branches
update-doc-branches: Documentation/all
	dev/update-doc-branches refs/heads/man refs/heads/html

# push the pregenerated doc files to origin/man and origin/html
push-docs: export-docs
	git push origin man html

# import pregenerated doc files from origin/man and origin/html, in case you
# don't have pandoc but still want to be able to install the docs.
import-docs: Documentation/clean
	$(pf); git archive origin/html | (cd Documentation && tar -xvf -)
	$(pf); git archive origin/man | (cd Documentation && tar -xvf -)

clean: Documentation/clean dev/python
	cd config && rm -rf config.var
	cd config && rm -f \
	  ${CONFIGURE_DETRITUS} ${CONFIGURE_FILES} ${GENERATED_FILES}
	rm -rf $(clean_paths) .pytest_cache
	find . -name __pycache__ -exec rm -rf {} +
	if test -e test/mnt; then dev/cleanup-mounts-under test/mnt; fi
	if test -e test/mnt; then rm -r test/mnt; fi
	if test -e test/tmp; then dev/cleanup-mounts-under test/tmp; fi
        # FIXME: migrate these to test/mnt/
	if test -e test/int/testfs; \
	  then umount test/int/testfs || true; fi
	rm -rf test/int/testfs test/int/testfs.img testfs.img
	if test -e test/tmp; then dev/force-delete test/tmp; fi
	dev/configure-sampledata --clean
        # Remove last so that cleanup tools can depend on it
	rm -f dev/python
