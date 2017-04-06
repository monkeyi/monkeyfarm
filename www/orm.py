#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio, logging
import aiomysql
import sys
import pdb
import logging
logging.basicConfig(level=logging.INFO)


# 日志输出
def log(sql, args=()):
    logging.info('SQL: %s' % sql)

# 创建连接池，以便尽量复用每个HTTP请求过程中使用的数据库连接
@asyncio.coroutine
def create_pool(loop, **kw):
    logging.info('create database connection pool...')
    # 定义全局变量，保存已经创建的连接
    global __pool
    __pool = yield from aiomysql.create_pool(
            # 从**kw中获取构造连接所需要的参数
            host=kw.get('host', '127.0.0.1'),
            port=kw.get('port', 3306),
            user=kw['user'],
            password=kw['password'],
            db=kw['db'],
            charset=kw.get('charset', 'utf8'),
            autocommit=kw.get('autocommit', True),
            maxsize=kw.get('maxsize', 10),
            minsize=kw.get('minsize', 1),
            loop=loop
     ) 
    logging.info('__pool = %s', __pool)

@asyncio.coroutine
def destroy_pool():
    global __pool
    if __pool is not None:
       __pool.close()
       yield from __pool.wait_closed()


# 封装数据库查询方法
@asyncio.coroutine
def select(sql, args, size=None):
    log(sql, args)
    global __pool
    # 从连接池中复用数据库连接
    with (yield from __pool) as conn:
        logging.info('select function, __pool=%s', __pool)
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args or ())
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
        logging.info('rows returned: %s' % len(rs))
        return rs

# 数据库Inset, Updata, Delete
# 返回操作影响的行数
@asyncio.coroutine
def execute(sql, args):
    log(sql)
    with (yield from __pool) as conn:
        logging.info('yield from __pool success, begain to excute function, __pool=%s', __pool)
        try:
            cur = yield from conn.cursor()
            yield from cur.execute(sql.replace('?', '%s'), args)
            affected = cur.rowcount
            logging.info('execute sql=%s, args=%s, affected=%s' % (sql, args,affected))
            yield from cur.close()
        except BaseException as e:
            logging.info('exception to get conn, e = %s', e)
            raise
        return affected

# 根据输入参数生成占位符列表
def create_args_string(num):
    L = []
    for n in range(num):
        L.append('?')
    # 以','为分隔符，将列表合成字符串
    return (','.join(L))


# -*- ModelMetaclass
# ModelMetaclass, 建立子类中的属性名称到数据库的字段的映射关系
class ModelMetaclass(type):

    def __new__(cls, name, bases, attrs):
        #logging.info('ModelMetaclass __new__, cls=%s, name=%s, bases=%s, attrs=%s' % (cls, name, bases, attrs))
        ''' 各参数的值如下，该方法在构造User类时会调用两次，name分别是Model, 和User，attrs的值为两者内部定义的成员的映射关系集合，因为我们只需要将Model的子类映射到数据库的表，所以后面的操作针对User的attrs。
        
            NFO:root:ModelMetaclass __new__, cls=<class '__main__.ModelMetaclass'>, name=Model, bases=(<class 'dict'>,), attrs={'__module__': '__main__', '__qualname__': 'Model', '__init__': <function Model.__init__ at 0x1031f48c8>, '__getattr__': <function Model.__getattr__ at 0x1031f4950>, '__setattr__': <function Model.__setattr__ at 0x1031f49d8>, 'getValue': <function Model.getValue at 0x1031f4a60>, 'getValueOrDefault': <function Model.getValueOrDefault at 0x1031f4ae8>, 'find': <classmethod object at 0x103178198>, 'findAll': <classmethod object at 0x103178208>, 'findNumber': <classmethod object at 0x103178240>, 'save': <function Model.save at 0x1031f4d08>, 'update': <function Model.update at 0x1031f4d90>, 'remove': <function Model.remove at 0x1031f4ea0>, '__classcell__': <cell at 0x1031a7a38: empty>}
            INFO:root:ModelMetaclass __new__, cls=<class '__main__.ModelMetaclass'>, name=User, bases=(<class '__main__.Model'>,), attrs={'__module__': '__main__', '__qualname__': 'User', 'id': <__main__.IntegerField object at 0x1031ee5f8>, 'name': <__main__.StringField object at 0x1031ee630>, 'sex': <__main__.StringField object at 0x1031ee668>, 'email': <__main__.StringField object at 0x1031ee6a0>, 'password': <__main__.StringField object at 0x1031ee6d8>}
        '''
        if name=='Model':
            return type.__new__(cls, name, bases, attrs)
        tableName = attrs.get('__table__', None) or name
        logging.info('found model: %s (talbe: %s)' % (name, tableName))

        # 建立映射关系并存储到子类的属性中
        mappings = dict()
        fields = []
        primaryKey = None

        for k, v in attrs.items():
            if isinstance(v, Field):
                logging.info('  found mappings: %s ==> %s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        #logging.info('after for, attrs=%s, field=%s' % (attrs, fields))
        '''
        root:after for, attrs={'__module__': '__main__', '__qualname__': 'User', 'id': <__main__.IntegerField object at 0x10ae5e630>, 'name': <__main__.StringField object at 0x10ae5e668>, 'sex': <__main__.IntegerField object at 0x10ae5e6a0>, 'email': <__main__.StringField object at 0x10ae5e6d8>, 'password': <__main__.StringField object at 0x10ae5e710>}, field=['name', 'sex', 'email', 'password']
        '''

        if not primaryKey:
            raise RuntimeError('Primary key not found.')
        for k in mappings.keys():
            attrs.pop(k)
        
        escaped_fields = []
        templist = []
        fieldname=None
        for name in fields:
            fieldname = (mappings.get(name).name or name)
            templist.append(fieldname)
            escaped_fields = list(map(lambda f: '`%s`' % f, templist))
        #escaped_fields = list(map(lambda f in fields: '`%s`' % (mappings.get(f).name or f), fields)
        #escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        logging.info('escaped_fields = %s, fields = %s, attrs = %s' % (escaped_fields, fields, attrs))
        '''
        INFO:root:escaped_fields = ['`name`', '`sex`', '`email`', '`password`'], fields = ['name', 'sex', 'email', 'password'], attrs = {'__module__': '__main__', '__qualname__': 'User'}
        '''
        attrs['__mappings__'] = mappings 
        attrs['__table__'] = tableName
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey
                , ', '.join(escaped_fields), tableName)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName, ', '.join(map(lambda f: '`%s`=?' % (mappings.get(f).name or f), fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName, primaryKey)
        #logging.info('before return type.__new__, attrs=%s' % (attrs,))
        '''
        INFO:root:before return type.__new__, attrs={'__module__': '__main__', '__qualname__': 'User', '__mappings__': {'id': <__main__.IntegerField object at 0x10ae5e630>, 'name': <__main__.StringField object at 0x10ae5e668>, 'sex': <__main__.IntegerField object at 0x10ae5e6a0>, 'email': <__main__.StringField object at 0x10ae5e6d8>, 'password': <__main__.StringField object at 0x10ae5e710>}, '__table__': 'User', '__primary_key__': 'id', '__fields__': ['name', 'sex', 'email', 'password'], '__select__': 'select `id`, `name`, `sex`, `email`, `password` from `User`', '__insert__': 'insert into `User` (`name`, `sex`, `email`, `password`, `id`) values (?,?,?,?,?)', '__update__': 'update `User` set `username`=?, `sex`=?, `email`=?, `password`=? where `id`=?', '__delete__': 'delete from `User` where = `id`=?'}
        '''
        return type.__new__(cls, name, bases,attrs)
# 定义ORM映射的基类
# Model类的任意子类可以映射一个数据库表
# 定义数据库操作方法，所有子类都可以直接使用
class Model(dict, metaclass=ModelMetaclass):

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
        #logging.info('Model __init_, self = %s, kw = %s' % (self, kw))

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                logging.debug('using default value for %s: %s' % (key, str(value)))
                setattr(self, key, value)
        return value

    # 数据库操作方法
    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        ' find object by primary key.'
        rs = yield from select('%s where `%s`=?' % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None, **kw):
        '''find objects by where clause'''
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        if args is None:
            args = []
        orderBy = kw.get('orderBy', None)
        if orderBy:
            sql.append('order by')
            sql.append(orderBy)

        limit = kw.get('limit', None)
        if limit is not None:
            sql.append('limit')
            if isinstance(limit, int):
                sql.append('?')
                args.append(limit)
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append('?,?')
                args.extend(limit)
            else:
                raise VauleError('Invalid limit value: %s' % str(limit))
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @classmethod
    @asyncio.coroutine
    def findNumber(cls, selectField, where=None, args=None):
        '''find number by select and where.'''
        sql = ['select %s __num__ from `%s`' % (selectField, cls.__table__)]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]['__num__']


    # 对象方法
    @asyncio.coroutine
    def save(self):
        logging.info('save start, begin to execute...')
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = yield from execute(self.__insert__, args)
        logging.info('save end, rows = %s', rows)
        
        if rows != 1:
            logging.warn('failed to insert record: affected rows: %s' % rows)
            
    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = yield from execute(self.__update__, args)
        if rows != 1:
            logging.warn('failed to update by primary key: %s, affected rows: %s' % (rows, self.__primary_key__))

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)
        if rows != 1:
            logging.warn('failed to remove by primary key: affected rows: %s' % rows)


# 抽象定义数据库字段类型
# 用于描述字段的名称，类型，是否是主键以及默认值
class Field(object):
    
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s, %s:%s>' % (self.__class__.__name__, self.column_type, self.name)

# 数据库字段字符串类型
class StringField(Field):

    def __init__(self, name=None, primary_key=False, default=None, ddl='varchar(20)'):
        super().__init__(name, ddl, primary_key, default)

# 数据库字段整型
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, 'int(4)', primary_key, default)

# 数据库字段浮点类型
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, 'float', primary_key, default)

# 数据库字段布尔类型
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'Boolean', False, default)

# 数据库字段文本类型
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, 'text', False, default)


# Test
#if __name__ == '__main__':
#    class User(Model):
#        id = IntegerField('id', primary_key=True)
#        name = StringField('username')
#        sex = IntegerField('sex')
#        email = StringField('email')
#        password = StringField('password')
#
#loop = asyncio.get_event_loop()
#
#@asyncio.coroutine
#def test():
#    yield from create_pool(loop=loop, host='127.0.0.1', port=3306, user = 'root', password='123456', db='test')
##    u = User(id=3, name='cccc', sex = 0, email='ccc@python.org', password='3333')
##    yield from u.save()
#
#    r = yield from User.findAll()
#    print(r)
#    
#    if len(r) != 0:
#        for user in r:
##            if user.id == 2:
##                user.name = 'abc'
##                user.email = 'abc@sina.com'
##                yield from user.update()
#             if user.id == 2:
#                 yield from user.remove()
#        r = yield from User.findAll()
#        print(r)
#
#    yield from destroy_pool()
#
#loop.run_until_complete(test())
#loop.close()
#if loop.is_closed():
#    sys.exit(0)

