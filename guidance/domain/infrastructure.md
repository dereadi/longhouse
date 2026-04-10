# Infrastructure Guidance

- Use FreeIPA NOPASSWD sudo: systemctl, tee, cat, cp, chmod, mkdir available.
- WireGuard IPs: bluefin=10.100.0.2, greenfin=10.100.0.3, owlfin=10.100.0.5, eaglefin=10.100.0.6
- Silverfin (FreeIPA server): 192.168.10.10
- Deploy services via: sudo tee for service files, sudo systemctl daemon-reload + start.
- RTX 6000 (96GB) is in redfin. RTX 5070 (12GB) is in bluefin. Do NOT confuse them.
- Greenfin runs BitNet ternary reflex (DC-10) + Cherokee 8B. No GPU.
- bmasass: M4 Max 128GB, Llama 70B (8801), Qwen3 30B (8800).
