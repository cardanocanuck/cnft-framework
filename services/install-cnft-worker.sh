cp cnft-worker.service /etc/systemd/system/cnft-worker.service
systemctl daemon-reload
systemctl enable cnft-worker.service
service cnft-worker restart
