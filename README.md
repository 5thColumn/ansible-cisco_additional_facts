# Introduction to ansible-cisco_additional_facts
This Ansible module is intended to gather more detailed facts about Cisco devices, such as route tables, MAC address tables, VRFs, and more. Currently supports IOS and NX-OS devices. It also adds a gather interfaces function that actually works properly for NX-OS devices as opposed to the default gather_facts module that does not properly gather interface details.
## Dependencies
You will first need to install the Python packages in the requirements.txt file. You can do this with: `pip install -r requirements.txt`. Then, you will need the cisco.ios and cisco.nxos Ansible collections installed to run this module. You can install these with: `ansible-galaxy collection install cisco.ios cisco.nxos`.
Finally, copy cisco_additional_facts.py into `$HOME/.ansible/plugins/modules`, which will make it available for Ansible to find and use the module.
## Module Arguments
#### fact_type
* Description: Specify the type of fact(s) to gather.
* Supported types: all, interfaces, inventory, license, mac_address_table, routes, route_neighbors, vrfs
* Required: False
* Default: all
* __Note: Recommend not using "all" as it will often result in a command timeout due to long-running operations. If you do need to run more than one fact type, it is best to run this module multiple times, once for each fact type.__
## Setup and Test
To test, I recommend using the Cisco Modeling Labs sandbox lab on Cisco Devnet, since it contains IOS and NX-OS devices already. When you run the ansible commands below, you will be prompted for the SSH password.
```
cd ansible-cisco_additional_facts
source ansible_env
ansible all -i INSERT_IP_ADDRESS_OR_DOMAIN_NAME, -c ansible.netcommon.network_cli -u INSERT_SSH_USERNAME -k -m cisco_additional_facts -e ansible_network_os=cisco.ios.ios -a fact_type=license
ansible all -i INSERT_IP_ADDRESS_OR_DOMAIN_NAME, -c ansible.netcommon.network_cli -u INSERT_SSH_USERNAME -k -m cisco_additonal_facts -e ansible_network_os=cisco.nxos.nxos -a fact_type=interfaces
```

[![published](https://static.production.devnetcloud.com/codeexchange/assets/images/devnet-published.svg)](https://developer.cisco.com/codeexchange/github/repo/5thColumn/ansible-cisco_additional_facts)
