.PHONY: test eval run

test:
	python -m unittest discover -s tests -p 'test_[!h]*.py' -v

eval:
	python -m tests.holdout_report
	python -m tests.fresh_holdout_report

run:
	python app.py
