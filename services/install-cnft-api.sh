cp cnft-api.service /etc/systemd/system/cnft-api.service
systemctl daemon-reload
systemctl enable cnft-api.service
service cnft-api restart
