#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging; logging.basicConfig(level=logging.INFO)
#import pdb

import asyncio, os, json, time

from datetime import datetime
from aiohttp import web

from jinja2 import Environment, FileSystemLoader

import orm
from coroweb import add_routes, add_static, add_route

def init_jinja2(app, **kw):
    logging.info('init jinja2..., kw = %s', (kw))
    options = dict(
            autoescape = kw.get('autoescape', True), 
            block_start_string = kw.get('block_start_string', '{%'),
            block_end_string = kw.get('block_end_string', '%}'),
            variable_start_string = kw.get('variable_start_string', '{{'),
            variable_end_string = kw.get('variable_end_string', '}}'),
            auto_reload = kw.get('auto_reload', True)
            )
    path = kw.get('path', None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    logging.info('set jinja2 template path: %s' % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kw.get('filters', None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app['__templating__'] = env

# 日志拦截器，当发起请求时，app会调用该函数并传入response_factory作为handler
# 在调用url处理函数之前会记录当前处理的请求方法和路径
async def logger_factory(app, handler):
    async def logger(request):
        logging.info('logger_factor, Request: %s %s, handler: %s app: %s' % (request.method, request.path, handler, app))
        return (await handler(request))
    return logger


# 请求拦截器，当发起请求时，会被app调用并传入
# 该函数hh用于拦截post请求将请求体数据正确的保存到request.__data__中
async def data_factory(app, hanlder):
    async def parse_data(request):
        if request.method == 'POST':
            if request.content_type.startswith('application/json'):
                request.__data__ = await request.json()
                logging.info('request json: %s' % str(request.__data__))
            elif request.content_type.startswith('application/x-www-form-urlencoded'):
                request.__data__ = await request.post()
                logging.info('request form: %s' % str(request.__data__))
        return (await handler(request))
    return parse_data

# response 拦截器, app在请求后会调用该函数，并传入add_router里面的url处理函数作为handler
# 该函数主要用于将实际处理函数的返回值此时为dict，转换成aiohttp框架需要的web.Response对象返回
async def response_factory(app, handler):
    async def response(request):
        logging.info('response_factory run, handler = %s', handler)
        r = await handler(request)
        logging.info('response_factory after handler result = %s', r)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = 'application/octet-stream'
            return resp
        if isinstance(r, str):
            if r.startswith('redirect:'):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(r, dict):
            template = r.get('__template__')
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode('utf-8'))
                resp.content_type = 'application/json;charset=utf-8'
                return resp
            else:
                resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
        if isinstance(r, int) and r >= 100 and r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and t >= 100 and t < 600:
                return web.Response(t, str(m))
        #default:
        resp = web.Response(body=str(r).encode('utf-8'))
        resp.content_type = 'text/plain;charset=utf-8'
        return resp
    return response


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

def index(request):
#    pdb.set_trace()
    return web.Response(body=b'<h1>Welcome to MonkeyFarm</h1>', content_type='text/html', charset='UTF-8')

async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='root', password='111111', db='monkeyfarm')
    # 创建应用程序对象, 并指定拦截器
    # app = web.Application(loop=loop)
    # 发起一个请求的程序执行步骤：
    # 发起请求-> app回调logger_factory(app, handler=response_factory) 该函数主要添加日志 -> response_factory(app, handler=RequestHandler), RequestHandler为app.add_router上的处理函数,它负责解析request参数给实际的url处理函数使用， 该response_factory函数先调用handler(request)得到处理后的结果，此时为dict对象，然后将dict转成web.Response对象以满足aiohttp框架的要求, 此web.Response为jinja2模板数据.
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
        ])
    # 初始化模板
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    # 将handler模块的url处理函数注册到app中
    add_routes(app, 'handlers')
    #index.__route__ = '/'
    #index.__method__ = 'GET'
    #add_route(app, index)
    add_static(app)
    # 创建tcp服务器
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000')
#    app = web.Application(loop=loop)
#    app.router.add_route('GET', '/', index)
#    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 9000)
#    logging.info('server started at http://127.0.0.1:9000...')
#    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
