# ASUS aggressive automatic cooling

For this ZenBook UX331UAL, requests the firmware full-speed mode when the
hottest Intel CPU sensor reaches 75°C. Returns to firmware automatic below
65°C and holds its previous mode in between. Checks every two seconds.
The reported 25,500 RPM in full-speed mode is not used for decisions.

Install and start (also starts on subsequent boots):

```bash
sudo bash /home/asus/fan-controller/install.sh
```

Check status and recent mode changes:

```bash
systemctl status asus-fan-controller.service --no-pager
journalctl -u asus-fan-controller.service -n 20 --no-pager
```

Disable and restore normal automatic cooling:

```bash
sudo systemctl disable --now asus-fan-controller.service
```

Stopping restores firmware automatic control. Sensor failures also restore
automatic control, then systemd retries after five seconds. An extra stop
command attempts restoration even if the main process is killed. A system
freeze or firmware/write failure can prevent software cleanup.

The controller manages the fan while running, so stop it before using manual
fan commands or another fan-control program. It cannot set intermediate RPM.
