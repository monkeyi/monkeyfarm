# url 处理函数

import re, time, json, logging, hashlib, base64, asyncio

from coroweb import get, post

from models import User, Comment, Blog, next_id

@get('/')
async def index(request):
    logging.info('index begin run')
    summary = 'this is summary for the article'
    blogs = [
            Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
            Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
            Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
            ]
    return {
            '__template__': 'blogs.html',
            'blogs': blogs
            }

#    users = await User.findAll()
#    logging.info('index run, request: %s, %s, users = %s' % (request.method, request.path, users)) 
#    return {
#            '__template__': 'test.html',
#            'users': users
#            }
