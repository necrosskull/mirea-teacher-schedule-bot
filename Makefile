.PHONY: format
format:
	isort --force-single-line-imports bot
	autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place bot --exclude=__init__.py
	black bot
	isort bot

.DEFAULT_GOAL :=