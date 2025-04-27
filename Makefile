PYTHON_VERSION := 3.11
POSTGRES_VERSION := 14

BREW_BIN := brew
PY_BIN := python$(PYTHON_VERSION)

ifneq ($(shell which $(BREW_BIN) >/dev/null 2>&1 && echo 0 || echo 1),0)
	$(error Cannot find '$(BREW_BIN)', Make sure it is isntalled and the PATH is set up correctly)
endif

BREW_PACKAGES := pantsbuild/tap/pants aws-sam-cli awscli coreutils findutils gh jq pre-commit python@$(PYTHON_VERSION) postgresql@$(POSTGRES_VERSION)
BREW_CASK_PACKAGES := docker mongodb-compass

PRECOMMIT_MARKER := $(CURDIR)/.git/hooks/pre-commit

BREW_PREFIX := $(shell brew --prefix)
BREW_CELLAR := $(BREW_PREFIX)/Cellar
BREW_CASKROOM := $(BREW_PREFIX)/Caskroom

BREW_MARKERS := $(addprefix $(BREW_CELLAR)/,$(BREW_PACKAGES))
BREW_CASK_MARKERS := $(addprefix $(BREW_CASKROOM)/,$(BREW_CASK_PACKAGES))

VENV_DIR := $(CURDIR)/venv
VENV_BIN_DIR := $(VENV_DIR)/bin
VENV_REQS := $(CURDIR)/requirements.txt

VENV_MARKER := $(VENV_BIN_DIR)/activate
REQS_MARKER := $(VENV_DIR)/requirements-isntalled

.PHONY: install
install: install_packages install_deps install_hooks

.PHONY: install_packages
install_packages: $(BREW_MARKERS) $(BREW_CASK_MARKERS)


$(BREW_MARKERS):
	brew install "$(subst $(BREW_CELLAR)/,,$@)"

$(BREW_CASK_MARKERS):
	brew install --cask "$(subst $(BREW_CASKROOM)/,,$@)"

.PHONY: venv
venv: $(VENV_MARKER)

$(VENV_MARKER):
	$(PY_BIN) -m venv "$(VENV_DIR)" && $(VENV_BIN_DIR)/$(PY_BIN) -m pip install -U pip

.PHONY: install_deps
install_deps: venv $(REQS_MARKER)

$(REQS_MARKER):
	$(VENV_BIN_DIR)/$(PY_BIN) -m pip install -r $(VENV_REQS) && \
	/usr/bin/touch $(REQS_MARKER)

.PHONY: install_hooks
install_hooks: install_deps $(PRECOMMIT_MARKER)

$(PRECOMMIT_MARKER):
	pre-commit install

.PHONY: shell
shell: install_deps
	/bin/bash --init-file "$(VENV_MARKER)" -i
