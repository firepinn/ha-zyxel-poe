[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

Manage the Power-over-Ethernet functionality of ZyXEL switches.
Because this functionality is not available via SNMP it will be performed over HTTP. Admin password is required.

## Acknowledgements

This plugin is inspired by https://github.com/lukas-hetzenecker/home-assistant-zyxel-poe which should work for some other models not supported by this plugin

## Compatibility

Tested with: 

- ZyXEL GS1200-5HP v2

Should be compatible with similar models like the ZyXEL GS1200-8HP v2.

## What works now?

The plugin creates a switch entity for each POE port as well as a sensor entity displaying the current power consumption for each port.

Because the plugin uses admin credentials and the Zyxel switch only allows one active user at the same time you will not be able to access the switch webui while the plugin is running

The webserver on the Zyxel switch also seems to be somewhat unstable which means sometimes requests get terminated without sending any response. The plugin will currently retry actions once and then give up

## How to get it running

1. Install this custom component through HACS or manually cloning the repo
2. Go to Configuration > Integrations
3. Add an integration, search for Zyxel POE switch, and click on it
4. Follow the wizard
