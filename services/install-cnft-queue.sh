cp cnft-queue.service /etc/systemd/system/cnft-queue.service
systemctl daemon-reload
systemctl enable cnft-queue.service
service cnft-queue restart
