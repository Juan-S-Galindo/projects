# Projects

Personal monorepo to organise and test projects, built with [Pants](https://www.pantsbuild.org/) (v2.25.1) on Python 3.11.

---

## Repository structure

```
projects/
├── apps/
│   └── chase_cc_ingestor/      # Chase credit card CSV → PostgreSQL ingestor
├── aws/                        # AWS serverless applications
│   └── budgeting_app/          # Budgeting app (Lambda + S3 resources)
├── pants-plugins/
│   └── serverless/             # Custom Pants plugin for Serverless Framework deployments
│       └── plugin/
│           ├── target_types.py # `serverless` target type definition
│           ├── rules.py        # Pants rules (packaging / deploy)
│           ├── subsystem.py    # Plugin subsystem
│           └── serverless_templates/
│               └── serverless.yml.tmpl
├── projects/
│   └── ut_data_viz_bootcamp/   # UT Data Visualisation Bootcamp challenges
│       └── python/
│           ├── challenge_python/    # PyBank & PyPoll (CSV analysis)
│           ├── challenge_pandas/    # HeroesOfPymoli & PyCitySchools
│           ├── challenge_matplotlib/# Pymaceuticals drug study plots
│           ├── challenge_sqlalchemy/# Hawaii climate Flask API
│           └── challenge_api/       # WeatherPy & VacationPy (external APIs)
├── internal/
│   └── pre_commit_hooks/       # Custom pre-commit hook scripts
├── Makefile                    # Dev environment bootstrap
├── pants.toml                  # Pants configuration
├── pyproject.toml              # Python tooling config (ruff, mypy)
├── requirements.txt            # Venv dependencies
└── serverless_global_config.yml.tmpl  # Global Serverless Framework config template
```

---

## Prerequisites

### Homebrew

Install Homebrew following the instructions at [https://brew.sh](https://brew.sh).

### Xcode Command Line Tools

```shell
xcode-select --install
```

### Git

```shell
brew install git
```

#### Git Large File Storage

```shell
brew install git-lfs
```

More info at [https://git-lfs.com](https://git-lfs.com).

#### GitHub SSH key

Follow the guide at [kbroman.org](https://kbroman.org/github_tutorial/pages/first_time.html) to generate and link an SSH key.

---

## Getting started

Run the bootstrap target to install all Homebrew packages, create the Python virtualenv, install Python dependencies, and set up pre-commit hooks:

```shell
make install
```

This installs the following Homebrew packages automatically:

| Package | Purpose |
|---|---|
| `pantsbuild/tap/pants` | Pants build system |
| `aws-sam-cli` | Local Lambda testing |
| `awscli` | AWS CLI |
| `serverless` | Serverless Framework CLI |
| `gh` | GitHub CLI |
| `jq` | JSON processing |
| `pre-commit` | Git hooks |
| `python@3.11` | Python runtime |
| `postgresql@18` | PostgreSQL |
| `docker` *(cask)* | Container runtime |
| `mongodb-compass` *(cask)* | MongoDB GUI |

To open a shell with the virtualenv activated:

```shell
make shell
```

---

## Pants build system

[Pants](https://www.pantsbuild.org/) is used for dependency management, linting, type checking, testing, and packaging across the monorepo.

Common commands:

```shell
# Lint all targets
pants lint ::

# Type-check all targets
pants check ::

# Run tests
pants test ::

# Package a binary
pants package <target>
```

---

## Custom Pants plugin — Serverless

Located in [pants-plugins/serverless/](pants-plugins/serverless/), this plugin adds a `serverless` target type that generates and deploys a `serverless.yml` from a Jinja2 template.

### `serverless` target fields

| Field | Type | Required | Description |
|---|---|---|---|
| `service` | `string` | Yes | CloudFormation stack name |
| `functions` | `list[address]` | No | Lambda function targets |
| `resources` | `list[address]` | No | AWS resource targets (S3, DynamoDB, etc.) |
| `config_files` | `list[address]` | No | Additional config file targets |
| `source_templates` | `list[address]` | No | Template targets (defaults to built-in template + global config) |
| `provider_config` | `dict` | No | Key/value pairs merged into the `provider:` block of `serverless.yml` |
| `custom_config` | `dict` | No | Key/value pairs merged into the `custom:` block |
| `import_gateway` | `dict` | No | Enables `serverless-import-apigateway` plugin and sets its config |
| `global_iam_statements` | `list[dict]` | No | IAM statements added to `provider.iamRoleStatements`; enables `serverless-iam-roles-per-function` |
| `s3_cleaner_bucket_names` | `list[string]` | No | S3 buckets to empty before stack removal |

Use `{{SERVICE_NAME}}` as a placeholder in any string value to reference the resolved stack name at render time.

---

## Projects

### UT Data Visualisation Bootcamp (`projects/ut_data_viz_bootcamp`)

A collection of data analysis challenges completed as part of the UT Data Visualisation Bootcamp:

| Challenge | Description |
|---|---|
| `challenge_python` | **PyBank** (profit/loss analysis) and **PyPoll** (election results) using pure Python |
| `challenge_pandas` | **HeroesOfPymoli** (game purchase analysis) and **PyCitySchools** (school district analysis) using Pandas |
| `challenge_matplotlib` | **Pymaceuticals** drug efficacy study visualised with Matplotlib |
| `challenge_sqlalchemy` | **Hawaii climate** analysis with SQLAlchemy ORM + Flask REST API |
| `challenge_api` | **WeatherPy** (OpenWeatherMap) and **VacationPy** (Geoapify) using external APIs |

### Chase Credit Card Ingestor (`apps/chase_cc_ingestor`)

Ingests Chase credit card CSV exports into a local PostgreSQL `expenses` database. Drop CSV statements into `apps/chase_cc_ingestor/statements/` and run:

```shell
brew services start postgresql@18

export PGHOST=localhost
export PGUSER=$(whoami)

pants run apps/chase_cc_ingestor:chase_cc_ingestor
```

See [apps/chase_cc_ingestor/README.md](apps/chase_cc_ingestor/README.md) for full setup instructions.

### Using the starter project

Try running the following commands:
- dbt run
- dbt test


### Resources:
- Learn more about dbt [in the docs](https://docs.getdbt.com/docs/introduction)
- Check out [Discourse](https://discourse.getdbt.com/) for commonly asked questions and answers
- Join the [chat](https://community.getdbt.com/) on Slack for live discussions and support
- Find [dbt events](https://events.getdbt.com) near you
- Check out [the blog](https://blog.getdbt.com/) for the latest news on dbt's development and best practices
