#!/bin/bash

cp -f /opt/octo-bots-python/data/octo-bots.service /etc/systemd/system/octo-bots.service
systemctl daemon-reload && systemctl enable octo-bots
systemctl start octo-bots --no-block
systemctl status octo-bots