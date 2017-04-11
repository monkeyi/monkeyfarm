# url 处理函数

import re, time, json, logging, hashlib, base64, asyncio

from coroweb import get, post

from models import User, Comment, Blog, next_id

@get('/')
async def index(request):
    logging.info('index begin run')
    users = await User.findAll()
    logging.info('index run, request: %s, %s, users = %s' % (request.method, request.path, users)) 
    return {
            '__template__': 'test.html',
            'users': users
            }
