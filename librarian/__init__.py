"""The librarian keeps catalog/flags/*.json true to the engines' own sources.

It works the way a careful person at a desk would: it reads what changed, files the additions that
cannot hurt, holds back anything that could change what the app does, writes down what it did, and
never throws away something it was not asked to. See `python3 -m librarian --help`.
"""
