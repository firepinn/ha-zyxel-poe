[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

Manage the Power-over-Ethernet functionality of ZyXEL switches.
Because this functionality is not available via SNMP it will be performed over HTTP. Admin credentials are required.

This plugin is inspired by https://github.com/lukas-hetzenecker/home-assistant-zyxel-poe which should work for some other models

# Compatibility

Tested with: 

- ZyXEL GS1200-5HP

Should be compatible with similar models like the ZyXEL GS1200-8HP.

## Installation 

To use this plugin, copy the `zyxel_switch_poe` folder into your [custom_components folder](https://developers.home-assistant.io/docs/en/creating_component_loading.html).

## Configuration 

```yaml
# Example configuration.yaml entry
switch:
- platform: zyxel_switch_poe
  devices:
  - host: switch1.local
    username: admin
    password: !secret switch1
  - host: switch2.local
    username: admin
    password: !secret switch2
```
