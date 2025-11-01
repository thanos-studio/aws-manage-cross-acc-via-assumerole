.PHONY: install runserver fmt lint

install:
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt

runserver:
	python manage.py migrate
	python manage.py runserver

fmt:
	black .
	isort .

lint:
	shellcheck scripts/*.sh
	python -m compileall scripts/
