#!/usr/bin/python
# -*- coding: utf-8 -*-
__author__ = 'nudzo'

DOCUMENTATION = '''
---
module: sunos_facts
short_description: Update facts with with info collected from OS
description:
  - Update facts with with info collected from OS to be used in forthcomming tasks
version_added: "1.1"
author: Ivan Nudzik
options:
  virtinfo:
    description:
      - Include virtinfo data
    required: false
    default: true
requirements:
  - At least Solaris 10 U11
notes:
  - State can be changed during time, merely when zone is in state *installing*
...
'''
EXAMPLES = '''
# Run it
- sunos_facts:
'''
import re
import platform

zparse_10_re = re.compile(r'^([\d\-]+):([\w\-_]+):(\w+):([\w\-_/]+):([\w\-]*):(\w+):(\w+)$')
zparse_11_re = re.compile(r'^([\d\-]+):([\w\-_]+):(\w+):([\w\-_/]+):([\w\-]*):(\w+):(\w+):([\w\-]*):(\w+):(\w*)$')
rls = platform.release()
proc = platform.processor()


def main():
    result = {
        'changed': False,
        'ansible_facts': {
            'sunos': {
                'zonename': 'global',
                'zones': {},
            },
        }
    }
    module = AnsibleModule(
        argument_spec={
            'virtinfo': dict(required=False, default=True),
        },
        supports_check_mode=True
    )
    if get_platform() != 'SunOS':
        module.fail_json(msg="This module is only for Solaris OS.")
    vinf = str(module.params.pop('virtinfo'))
    znamec = [module.get_bin_path('zonename', True), ]
    rc, zname, err = module.run_command(znamec, check_rc=True)
    if rc != 0:
        module.fail_json(msg="Failed to discover Solaris zonename: %s" % err)
    if 'global' in zname:
        # zones list
        cmd = [module.get_bin_path('zoneadm', True), 'list', '-pic']
        rc, out, err = module.run_command(cmd, check_rc=True)
        if rc != 0:
            module.fail_json(msg="Failed to discover Solaris zones: %s" % err)
        for zone in out.split("\n"):
            if rls == '5.10':
                rmatch = zparse_10_re.match(zone)
            else:
                rmatch = zparse_11_re.match(zone)
            if rmatch:
                try:
                    zid = int(rmatch.group(1))
                except ValueError:
                    zid = -1
                zdict = dict(
                    zoneid=zid,
                    zonename=rmatch.group(2),
                    state=rmatch.group(3),
                    zonepath=rmatch.group(4),
                    uuid=rmatch.group(5),
                    brand=rmatch.group(6),
                    ip_type=rmatch.group(7)
                )
                if rls == '5.11':
                    zdict.update(dict(
                        rw=rmatch.group(8),
                        file_mac_profile=rmatch.group(9)
                    ))
                result['ansible_facts']['sunos']['zones'][rmatch.group(2)] = zdict
        # virtualization info
        if proc == 'sparc':
            cmd = [module.get_bin_path('virtinfo', True), '-a', ]
            rc, out, err = module.run_command(cmd, check_rc=True)
            if rc != 0:
                module.fail_json(msg="Failed to discover virtual info #1: %s" % err)
            vinf = {}
            for oline in out.split("\n"):
                if oline == "":
                    continue
                try:
                    olns = oline.split(":")
                    vk = olns[0].strip()
                    vv = olns[1].strip()
                except IndexError:
                    module.fail_json(msg=oline)
                if vk == "Domain name":
                    vinf.update(dict(domain_name=vv))
                elif vk == "Domain UUID":
                    vinf.update(dict(domain_uuid=vv))
                elif vk == "Control domain":
                    vinf.update(dict(control_domain=vv))
                elif vk == "Chassis serial#":
                    vinf.update(dict(chassis_serial=vv))
            cmd = [module.get_bin_path('virtinfo', True), '-p', ]
            rc, out, err = module.run_command(cmd, check_rc=True)
            if rc != 0:
                module.fail_json(msg="Failed to discover virtual info #2: %s" % err)
            oline = out.split("\n")
            drole = {}
            try:
                for role in oline[1].split("|"):
                    kv = role.split("=")
                    if kv.__len__() == 2:
                        drole[kv[0]] = True if kv[1] == "true" else False
            except IndexError:
                module.fail_json(msg="Wrong output from virtinfo -p")
            vinf.update(dict(domain_role=drole))
            result['ansible_facts']['sunos'].update(dict(virtinfo=vinf))
    else:
        result['ansible_facts']['sunos']['zonename'] = zname.strip()
    result['ansible_facts']['sunos']['processor'] = proc
    cmd = [module.get_bin_path('hostid', True),]
    rc, out, err = module.run_command(cmd, check_rc=True)
    if rc != 0:
        module.fail_json(msg="Failed to Solaris hostid: %s" % err)
    result['ansible_facts']['sunos']['hostid'] = out.strip()
    module.exit_json(**result)


# import module snippets
from ansible.module_utils.basic import *

if __name__ == '__main__':
    main()
