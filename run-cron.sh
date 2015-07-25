#!/bin/bash

echo ''
date
env $(cat /home/fiatjaf/comp/wft/.prod.env | xargs) /home/fiatjaf/comp/wft/model-updates/venv/bin/python /home/fiatjaf/comp/wft/model-updates/reader.py >> /home/fiatjaf/comp/wft/model-updates/cron.log 2>&1
