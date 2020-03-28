# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line.
# $ make -e SPHINXOPTS="th123"
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = th123discord
SOURCEDIR     = source
BUILDDIR      = ./
# for i18n
SPHINXINTL    = sphinx-intl
LANGUAGE      = en
LOCALEDIR     = $(SOURCEDIR)/locale/$(LANGUAGE)/LC_MESSAGES/
I18NDIR       = $(BUILDDIR)/$(LANGUAGE)/
POTDIR        = $(BUILDDIR)/_gettext/
SPHINXOPTS_   = -D language=$(LANGUAGE) -D html_copy_source=0 $(SPHINXOPTS) $(O)

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

.PHONY: html
html:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR)."

.PHONY: en
en:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(I18NDIR)" $(SPHINXOPTS_)
	@echo
	@echo "Build finished. The HTML pages are in $(I18NDIR) using PO files in $(LOCALEDIR)."

.PHONY: pot
pot:
	@$(SPHINXBUILD) -b gettext "$(SOURCEDIR)" "$(POTDIR)"
	@echo
	@echo "Checking update for $(LOCALEDIR) ..."
	@$(SPHINXINTL) update -p "$(POTDIR)"
	@echo "Build finished. The latest PO files are in $(LOCALEDIR)."

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

