#!/bin/sh
set -eu
cp -R /src /tmp/package
cd /tmp/package
python -m pip install --quiet '.[test]' build
python -m pytest -q
python -m build > /tmp/build.log
python -m pip install --quiet --force-reinstall --no-deps dist/*.whl
cd /tmp
python -c 'from langchain_mailchannels import MailChannelsSendEmailTool; assert MailChannelsSendEmailTool.__module__ == "langchain_mailchannels.tool"'
