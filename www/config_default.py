#!/usr/bin/env python3

# -*- coding: utf-8 -*-

'''
Default configuration.
'''

__author__ = 'Neo li'

configs = {
        'debug': True, 
        'db': {
            'host':'127.0.0.1',
            'port': 3306, 
            'user': 'root',
            'password': '111111',
            'db': 'monkeyfarm'
            },
        'session': {
            'secret': 'Awesome'
            }
        }

